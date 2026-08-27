"""Read image dimensions and EXIF metadata using Pillow."""
import argparse
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("file"); a=p.parse_args(argv)
    try:
        from PIL import Image
        with Image.open(a.file) as im: data={"file":a.file,"format":im.format,"size":im.size,"mode":im.mode,"exif":{str(k):str(v) for k,v in im.getexif().items()}}
    except Exception as e: data={"file":a.file,"error":str(e)}
    emit(data,a.json)
if __name__=="__main__": main()
