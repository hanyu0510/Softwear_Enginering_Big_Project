"""Generate local WebP course assets from already tracked project examples."""
from pathlib import Path
from PIL import Image

here = Path(__file__).resolve().parent
root = here.parent
target = root / 'backend/data/yida-classroom/state/media'
target.mkdir(parents=True, exist_ok=True)
source = root / 'preview/assets'
authors = list(source.glob('avatar_*.png'))
looks = list(source.glob('look_*.jpg'))
garments = [root / 'backend/demo_assets/realistic' / f'{name}.png' for name in (
    'cream-knit', 'blue-jeans', 'khaki-trench', 'white-sneakers', 'brown-bag',
    'floral-dress', 'burgundy-scarf', 'denim-overshirt',
)]
assert len(looks) == 12 and len(authors) == 7
for path in authors + looks + garments:
    result = target / (path.stem.replace('_', '-') + '.webp')
    if result.exists() and result.stat().st_mtime_ns >= path.stat().st_mtime_ns:
        continue
    with Image.open(path) as file:
        image = file.convert('RGB')
        maximum = 180 if path in authors else 880
        image.thumbnail((maximum, maximum))
        image.save(result, quality=83)
