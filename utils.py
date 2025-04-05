from PIL import Image

def save_grid_to_image(grid, filename):
    if not grid:
        return
    h = len(grid)
    w = len(grid[0])
    img = Image.new("RGB", (w, h), (255, 255, 255))
    for y in range(h):
        for x in range(w):
            c = grid[y][x].lstrip('#')
            if len(c) == 6:
                r = int(c[0:2], 16)
                g = int(c[2:4], 16)
                b = int(c[4:6], 16)
            else:
                r,g,b = 0,0,0
            img.putpixel((x,y),(r,g,b))
    img.save(filename)
    print(f"[INFO] Grid saved to {filename}")