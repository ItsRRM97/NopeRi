import base64
import os
'''Experimental nkparam generatin, working on this currently '''
def generate_nkparam() -> str:
    """Generate a random nkparam that looks like the real one (64 random bytes -> 88 char base64)"""
    return base64.b64encode(os.urandom(64)).decode()

# test
val = generate_nkparam()
print(len(val))   # 8
print(val)