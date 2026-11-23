import ctypes, shutil, sqlite3, os
src = r"C:\Users\Administrator\AppData\Roaming\linger\Network\Cookies"
dst = r"F:\AI\logs\cookies-copy.db"
shutil.copyfile(src, dst)
con = sqlite3.connect(dst)
rows = con.execute("select host_key,name,path,is_httponly,is_secure,expires_utc,length(encrypted_value),length(encrypted_value)>0 from cookies").fetchall()
for r in rows:
    print(r)
def dpapi(data):
    if data[:5] == b"DPAPI":
        data = data[5:]
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.c_char_p)]
    b_in, b_out = DATA_BLOB(len(data), ctypes.create_string_buffer(data, len(data))), DATA_BLOB()
    if ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(b_in), None, None, None, None, 0, ctypes.byref(b_out)):
        val = ctypes.create_string_buffer(b_out.pbData, b_out.cbData)
        out = val.raw[:b_out.cbData]
        ctypes.windll.kernel32.LocalFree(b_out.pbData)
        return out
    return None
cur = con.execute("select host_key,name,encrypted_value from cookies")
for host, name, enc in cur.fetchall():
    if not enc:
        print("PLAIN?", host, name)
        continue
    val = dpapi(enc)
    print("COOKIE", host, name, "=", (val[:80] if val else "DECRYPT-FAIL"))
