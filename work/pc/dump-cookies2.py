import ctypes, shutil, sqlite3, subprocess, time
subprocess.run(["taskkill", "/IM", "Linger.exe", "/T", "/F"], capture_output=True)
time.sleep(3)
src = r"C:\Users\Administrator\AppData\Roaming\linger\Network\Cookies"
dst = r"F:\AI\logs\cookies-copy.db"
shutil.copyfile(src, dst)
subprocess.run(["schtasks", "/run", "/tn", "pc_linger_start"], capture_output=True)
con = sqlite3.connect(dst)
def dpapi(data):
    if data[:5] == b"DPAPI":
        data = data[5:]
    class B(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("pb", ctypes.c_char_p)]
    bi, bo = B(len(data), ctypes.create_string_buffer(data, len(data))), B()
    if ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(bi), None, None, None, None, 0, ctypes.byref(bo)):
        buf = ctypes.create_string_buffer(bo.pb, bo.cb)
        out = buf.raw[:bo.cb]
        ctypes.windll.kernel32.LocalFree(bo.pb)
        return out
    return None
for host, name, path, secure, exp, enc in con.execute(
        "select host_key,name,path,is_secure,expires_utc,encrypted_value from cookies"):
    val = dpapi(bytes(enc)) if enc else b""
    print("COOKIE", host, name, "secure" if secure else "", "=", (val.decode("utf-8", "replace")[:100] if val else "FAIL"))
