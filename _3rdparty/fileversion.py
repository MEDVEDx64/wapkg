# Origin: http://code.activestate.com/recipes/67682-extracting-windows-file-versions/
# + porting to Python 3

VOS_DOS = 0x00010000
VOS_OS216 = 0x00020000
VOS_OS232 = 0x00030000
VOS_NT = 0x00040000
VOS__BASE = 0x00000000
VOS__WINDOWS16 = 0x00000001
VOS__PM16 = 0x00000002
VOS__PM32 = 0x00000003
VOS__WINDOWS32 = 0x00000004
VOS_DOS_WINDOWS16 = 0x00010001
VOS_DOS_WINDOWS32 = 0x00010004
VOS_OS216_PM16 = 0x00020002
VOS_OS232_PM32 = 0x00030003
VOS_NT_WINDOWS32 = 0x00040004


def normalizer(s):
    for j in range(len(s)):
        if len(s[j]) > 3:
            k = s[j][2:]
        else:
            k = '0' + s[j][2:]
        s[j] = k
    return s


def calcversioninfo(fn):
    ostypes = [VOS_DOS, VOS_NT, VOS__WINDOWS32, VOS_DOS_WINDOWS16,
               VOS_DOS_WINDOWS32, VOS_NT_WINDOWS32]

    verstrings = []
    sigstrings = findsignatures(fn)
    if sigstrings[0] == '':
        return None
    for i in sigstrings:
        fv = normalizer(i.split(',')[8:16])
        fos = normalizer(i.split(',')[32:36])
        hexver = fv[3]+fv[2]+fv[1]+fv[0]+':'+fv[7]+fv[6]+fv[5]+fv[4]
        os_tag = int('0x' + fos[3]+fos[2]+fos[1]+fos[0], 16)
        if os_tag not in ostypes:
            continue
        if hexver not in verstrings:
            verstrings.append(hexver)
    myver = max(verstrings)
    return parsver(myver)


def createparsestruct(b):
    s = ''
    for i in range(len(b)):
        s += hex(b[i])+','
    return s[:-1]


def findsignatures(file):
    f = open(file, 'rb')
    sz = f.read()
    f.close()
    res = []
    indx = sz.find(b'\xbd\x04\xef\xfe')
    cnt = sz.count(b'\xbd\x04\xef\xfe')
    while cnt > 1:
        s = createparsestruct(sz[indx:indx+52])
        sz = sz[indx+1:]
        cnt = sz.count(b'\xbd\x04\xef\xfe')
        indx = sz.find(b'\xbd\x04\xef\xfe')
        res.append(s)
    res.append(createparsestruct(sz[indx:indx+52]))
    return res


def parsver(v):
    a, b, c, d = v[:4], v[4:8], v[9:13], v[13:]
    return str(int(a, 16)) + '.' + str(int(b, 16)) + '.' + str(int(c, 16)) + '.' + str(int(d, 16))
