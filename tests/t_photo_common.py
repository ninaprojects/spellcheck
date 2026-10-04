import os
import io, sys, json, base64; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import piexif
def big_jpeg(w=4032, h=3024, orientation=6, gps=(34.0195,-118.4912), quality=95):
    rng = np.random.default_rng(7)
    base = rng.integers(0, 256, size=(h//8, w//8, 3), dtype=np.uint8)
    arr = np.kron(base, np.ones((8,8,1),dtype=np.uint8))
    arr = np.clip(arr.astype(np.int16) + rng.integers(-25, 25, size=arr.shape), 0, 255).astype(np.uint8)
    im = Image.fromarray(arr, 'RGB')
    def dms(v):
        d=int(v); m=int((v-d)*60); s=round(((v-d)*60-m)*60*100); return ((d,1),(m,1),(s,100))
    ex = {'0th':{piexif.ImageIFD.Orientation: orientation}}
    if gps:
        ex['GPS']={piexif.GPSIFD.GPSLatitudeRef:b'N' if gps[0]>=0 else b'S', piexif.GPSIFD.GPSLatitude:dms(abs(gps[0])), piexif.GPSIFD.GPSLongitudeRef:b'E' if gps[1]>=0 else b'W', piexif.GPSIFD.GPSLongitude:dms(abs(gps[1]))}
    b = io.BytesIO(); im.save(b,'jpeg',quality=quality,exif=piexif.dump(ex)); return b.getvalue()
def decode_dataurl(du):
    head, b64 = du.split(',',1); raw = base64.b64decode(b64); return raw, Image.open(io.BytesIO(raw))
