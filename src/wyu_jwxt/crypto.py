"""乘方教务系统登录密码加密。

算法（逆向自登录页第 874-877 行）：
    AES-128-ECB, Pkcs7 padding, 密钥 = verifycode × 4（16 字节）, 输出 hex
"""
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

__all__ = ["encrypt_password"]


def encrypt_password(password: str, verifycode: str) -> str:
    """对明文密码做乘方教务登录加密。

    Args:
        password: 明文密码
        verifycode: 验证码（4 字符；密钥由其重复 4 次构成 16 字节）

    Returns:
        hex 编码的密文字符串
    """
    key = (verifycode * 4).encode("utf-8")  # 16 字节
    cipher = AES.new(key, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(password.encode("utf-8"), AES.block_size))
    return encrypted.hex()
