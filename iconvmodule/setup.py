from distutils.core import setup, Extension

setup (name = "iconv",
       version = "1.0",
       description = "iconv-based Unicode converter",
       author = "Martin v. Loewis",
       author_email = "loewis@informatik.hu-berlin.de",
       url = "http://sourceforge.net/projects/python-codecs/",
       long_description =
"""The iconv module exposes the operating system's iconv character
conversion routine to Python. This package provides an iconv wrapper
as well as a Python codec to convert between Unicode objects and
all iconv-provided encodings.
""",

       py_modules = ['iconvcodec'],
       ext_modules = [Extension("iconv",sources=["iconvmodule.c"])]
       )

