import sys
import argparse
from pathlib import Path
import imageio
import PIL
import numpy as np

def read_all_badges(in_dir, count):
    size = 50
    for i in range(1, count+1):
        i_png = in_dir / f'{i}.png'
        img = imageio.v2.imread(i_png, format='PNG-PIL')
        img = PIL.Image.fromarray(img).resize((size,)*2)
        yield np.asarray(img)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("count", type=int)
    parser.add_argument("in_dir", type=Path)
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args()
    for d in [args.in_dir, args.out_dir]:
        if not d.is_dir():
            print(d, 'is not a folder')
            sys.exit(0)

    out_img = np.concatenate(list(
        read_all_badges(args.in_dir, args.count)
    ), 0)

    out_png = args.out_dir / 'badges.png'
    imageio.v2.imwrite(
        out_png, out_img, format='PNG-PIL'
    )
