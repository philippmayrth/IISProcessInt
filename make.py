import os

def convert(path: str):
    print(path)
    os.system(f"/Applications/draw.io.app/Contents/MacOS/draw.io --export -f svg -o build '{path}'")

if __name__ == "__main__":
    for root, dirs, files in os.walk("."):
        for f in files:
            if f.endswith(".drawio"):
                convert(os.path.join(root, f))
        