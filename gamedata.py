"""Game data from gamedata/data1.0.json (SatisfactoryTools, MIT): items, recipes, buildings + item display names.

Keys are class names ('Desc_Wire_C', 'Recipe_IronPlate_C', 'Desc_ConstructorMk1_C').
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, 'gamedata', 'data1.0.json')) as _f:
    GD = json.load(_f)
ITEMS, RECIPES, BUILDINGS, GENERATORS = GD['items'], GD['recipes'], GD['buildings'], GD['generators']

POWER_EXPONENT = 1.321929              # overclock power exponent (fallback when a building lacks one)
FLUID_BUFFER = 50                      # m³ a machine fluid output buffer holds

# names the dataset lacks (key without _C)
NAME_OVERRIDES = {'Desc_MotorTurbo': 'Turbo Motor', 'Desc_GoldenNut': 'Golden Nut Statue'}
FLUID_NAMES = {v['name'] for v in ITEMS.values() if v.get('liquid')}


def item_name(path):
    """'/Game/.../Desc_Wire.Desc_Wire_C' or 'Desc_Wire_C' → 'Wire' (fallback: class name split into words)."""
    if not path:
        return None
    k = path.split('.')[-1]
    base = k[:-2] if k.endswith('_C') else k
    it = ITEMS.get(base + '_C')
    if it:
        return it['name']
    if base in NAME_OVERRIDES:
        return NAME_OVERRIDES[base]
    return re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', re.sub(r'^(Desc_|BP_|Build_)', '', base))


def is_fluid(path):
    return bool(ITEMS.get(path.split('.')[-1], {}).get('liquid'))


def stack_size(key, default=100):
    return ITEMS.get(key, {}).get('stackSize', default)
