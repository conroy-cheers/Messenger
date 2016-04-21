from Crypto.Hash import SHA256
from Crypto.Cipher import AES
import os


class Message:
    def __init__(self, data, author='', decrypt=False, key=None):
        if decrypt:
            self.decrypt(data, key)
        else:
            self.IV = os.urandom(16)
            self.author = pad(bytes(author, encoding='utf-8'))
            self.author_len = len(bytes(author, encoding='utf-8'))
            self.data = pad(bytes(data, encoding='utf-8'))
            self.data_len = len(bytes(data, encoding='utf-8'))

    def encrypt(self, key):
        assert type(key) == bytes
        ciph = AES.new(key, AES.MODE_CBC, self.IV)
        self.data = b'\me' + self.IV + ciph.encrypt(self.data_len.to_bytes(16, byteorder='big') +
                                                    self.author_len.to_bytes(16, byteorder='big') +
                                                    self.author + self.data)
        self.data += SHA256.new(self.data).digest()
        return self.data

    def decrypt(self, bs, key):
        assert type(bs) == bytes
        assert type(key) == bytes
        assert bs[:3] == b'\me'
        self.IV = bs[3:19]
        checksum = bs[-32:]
        if checksum != SHA256.new(bs[:-32]).digest():
            # Checksum not matching
            return None
        ciph = AES.new(key, AES.MODE_CBC, self.IV)
        decrypt_message = ciph.decrypt(bs[19:-32])
        self.data_len = int.from_bytes(decrypt_message[:16], byteorder='big')
        self.author_len = int.from_bytes(decrypt_message[16:32], byteorder='big')
        self.author = decrypt_message[32:32 + self.author_len]
        self.data = decrypt_message[pad(self.author_len) + 32:pad(self.author_len) + 32 + self.data_len]
        return self.author, self.data

    def __str__(self):
        return str(self.author, encoding='utf-8') + ": " + str(self.data, encoding='utf-8')

    def __bytes__(self):
        return self.data


def pad(b):
    if type(b) == bytes:
        return b + b'\x00' * (16 - len(b) % 16)
    elif type(b) == int:
        return b + (16 - b % 16)
    else:
        raise TypeError("pad() only takes a single argument of type bytes or int.")


def hash_password(b):
    hash = SHA256.new(pad(bytes(b, encoding='utf-8')))
    return hash.digest()


def enc_chal(bs, key):
    IV = bs[16:]
    ciph = AES.new(key, AES.MODE_CBC, IV)
    return ciph.encrypt(bs[:16])


def random_chal():
    return os.urandom(32)


if __name__ == "__main__":
    nam = Message('a•§ Selfishness is the antithesis of wonder. You may be ruled by greed without realizing it. '
                  'Do not let it exterminate the truth of your mission. We can no longer afford to live with pain.')
    password = hash_password(input("Enter a password: "))
    nam.encrypt(password)
    print("encrypted data:", nam)
    nam.decrypt(nam.data, password)
    print("original message:", nam.data.decode(encoding='utf-8'))
