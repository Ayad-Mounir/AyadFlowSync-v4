#!/usr/bin/env python3
"""
security.secure_store — AES-256-GCM encrypted storage.
✅ FIX v4.1: استبدال CTR محلي (SHA-256 keystream) بـ AES-256-GCM الحقيقي
من مكتبة cryptography — مثبّتة أصلاً في المشروع.

AES-256-GCM يوفر:
  • سرية (encryption) ✅
  • صحة (authentication / tamper detection) ✅ — بدل HMAC خارجي
  • IV عشوائي 96-bit لكل save ✅ — لا خطر إعادة استخدام IV
"""
import os
import json
import logging
from pathlib import Path
from typing import Optional

from ..core.app_config import AppConfig

_logger = logging.getLogger("AyadFlowSync.security")

# ── حدود التشفير ─────────────────────────────────────────────
_ITERATIONS = 310_000   # PBKDF2-HMAC-SHA256 (NIST SP 800-132)
_KEY_LEN    = 32        # AES-256
_SALT_LEN   = 32
_IV_LEN     = 12        # GCM standard = 96 bits
_VERSION    = 4         # v4 = AES-GCM (v3 = SHA256-CTR)


def _aes_gcm_encrypt(key: bytes, iv: bytes, data: bytes) -> tuple[bytes, bytes]:
    """
    تشفير AES-256-GCM.
    Returns: (ciphertext, tag)
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    aesgcm = AESGCM(key)
    # AESGCM.encrypt يُرجع ciphertext + tag مدمجَين
    combined = aesgcm.encrypt(iv, data, None)
    # آخر 16 byte = tag
    ct, tag = combined[:-16], combined[-16:]
    return ct, tag


def _aes_gcm_decrypt(key: bytes, iv: bytes, ct: bytes, tag: bytes) -> bytes:
    """
    فك تشفير AES-256-GCM مع التحقق من صحة البيانات.
    يرفع InvalidTag إذا تغيّرت البيانات.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(iv, ct + tag, None)


class SecureStore:
    """
    ✅ v4.1 — AES-256-GCM encrypted key-value store.
    جميع الأسرار تمر من هنا — لا ملفات نص واضح.

    التغيير من v3:
      v3: SHA-256 كـ keystream (CTR محلي) + HMAC خارجي منفصل
      v4: AES-256-GCM الحقيقي — تشفير + authentication في عملية واحدة
    """

    _flash_secret: Optional[str] = None
    _master_pin:   Optional[str] = None

    @classmethod
    def set_master_pin(cls, pin: str):
        cls._master_pin = pin.strip() if pin else None

    @classmethod
    def clear_master_pin(cls):
        cls._master_pin = None

    @classmethod
    def _get_secret(cls) -> str:
        if cls._flash_secret:
            return cls._flash_secret
        secret_file = AppConfig.DATA_DIR / '.flash_secret'
        try:
            if secret_file.exists():
                val = secret_file.read_text().strip()
                if len(val) == 64:
                    cls._flash_secret = val
                    return val
            # إنشاء secret جديد
            secret = os.urandom(32).hex()
            AppConfig.DATA_DIR.mkdir(exist_ok=True)
            secret_file.write_text(secret)
            try:
                os.chmod(secret_file, 0o600)
            except Exception:
                pass
            cls._flash_secret = secret
            return secret
        except Exception:
            if not cls._flash_secret:
                cls._flash_secret = os.urandom(32).hex()
            return cls._flash_secret

    @classmethod
    def _derive_key(cls, salt: bytes) -> bytes:
        import hashlib
        password = cls._get_secret()
        if cls._master_pin:
            password += cls._master_pin
        return hashlib.pbkdf2_hmac(
            'sha256', password.encode(), salt, _ITERATIONS, dklen=_KEY_LEN
        )

    @classmethod
    def save(cls, filepath: Path, plaintext: str, extra: dict = None) -> bool:
        try:
            salt = os.urandom(_SALT_LEN)
            iv   = os.urandom(_IV_LEN)    # 96-bit GCM IV
            key  = cls._derive_key(salt)
            ct, tag = _aes_gcm_encrypt(key, iv, plaintext.encode('utf-8'))

            doc = {
                "v"   : _VERSION,
                "salt": salt.hex(),
                "iv"  : iv.hex(),
                "tag" : tag.hex(),
                "ct"  : ct.hex(),
            }
            if extra:
                doc["extra"] = extra

            filepath.parent.mkdir(parents=True, exist_ok=True)
            tmp = filepath.with_suffix(filepath.suffix + '.tmp')
            tmp.write_text(json.dumps(doc), encoding='utf-8')
            tmp.replace(filepath)
            try:
                os.chmod(filepath, 0o600)
            except Exception:
                pass
            return True

        except Exception as e:
            _logger.error(f"SecureStore.save: {e}")
            return False

    @classmethod
    def load(cls, filepath: Path) -> Optional[str]:
        try:
            if not filepath.exists():
                return None
            doc = json.loads(filepath.read_text(encoding='utf-8'))
            v   = doc.get("v", 1)

            if v >= 4:
                # ── AES-256-GCM (v4) ─────────────────────────────
                salt = bytes.fromhex(doc["salt"])
                iv   = bytes.fromhex(doc["iv"])
                ct   = bytes.fromhex(doc["ct"])
                tag  = bytes.fromhex(doc["tag"])
                key  = cls._derive_key(salt)
                try:
                    return _aes_gcm_decrypt(key, iv, ct, tag).decode('utf-8')
                except Exception:
                    _logger.warning("SecureStore: GCM authentication failed — tampered or wrong PIN")
                    return None

            elif v == 3:
                # ── Legacy v3: SHA256-CTR + HMAC ─────────────────
                # نقرأ ونُعيد حفظ بـ v4 تلقائياً (migration شفاف)
                import hmac as _hmac, hashlib as _hs
                salt = bytes.fromhex(doc["salt"])
                iv   = bytes.fromhex(doc["iv"])
                ct   = bytes.fromhex(doc["ct"])
                key  = cls._derive_key(salt)
                expected_mac = _hmac.new(key, ct, _hs.sha256).hexdigest()
                if not _hmac.compare_digest(expected_mac, doc.get("mac", "")):
                    _logger.warning("SecureStore v3: HMAC mismatch")
                    return None
                # فك تشفير CTR القديم
                out   = bytearray()
                ctr   = int.from_bytes(iv, 'big')
                for i in range(0, len(ct), 32):
                    block = _hs.sha256(key + ctr.to_bytes(16, 'big')).digest()
                    chunk = ct[i:i+32]
                    out.extend(b ^ k for b, k in zip(chunk, block[:len(chunk)]))
                    ctr += 1
                plaintext = bytes(out).decode('utf-8')
                # ترقية تلقائية إلى v4
                cls.save(filepath, plaintext, extra=doc.get("extra"))
                _logger.info(f"SecureStore: migrated {filepath.name} v3→v4")
                return plaintext

            else:
                # ── Legacy v1/v2 — plaintext ─────────────────────
                raw = filepath.read_text(encoding='utf-8').strip()
                if raw and not raw.startswith('{'):
                    cls.save(filepath, raw)
                    return raw
                return None

        except Exception as e:
            _logger.error(f"SecureStore.load: {e}")
            return None

    @classmethod
    def delete(cls, filepath: Path) -> None:
        filepath.unlink(missing_ok=True)

