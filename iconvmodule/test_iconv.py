import iconv
s=iconv.open("unicodelittle", "iso-8859-1")
r=s.iconv("Hallo")
print repr(r),len(r)

s=iconv.open("utf-8", "iso-8859-1")
r=s.iconv("Hallo")
print repr(r),len(r)
u = r.encode("utf-8")
print u

s=iconv.open("utf-8", "euc-jp")
r=s.iconv("testビデオカードを検出中test")
print repr(r),len(r)
u = r.decode("utf-8")
print repr(u)

s=iconv.open("euc-jp", "utf-8")
r=s.iconv(u)
print repr(r), len(r)
print r

s=iconv.open("iso-8859-1","unicodelittle")
r=s.iconv(u"Hallo")
print r
