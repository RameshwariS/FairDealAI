"""Generate a stand-in store.csv and policy.json.

These are SYNTHETIC files that follow the shape described in the AgentX
problem statement (~100 products with price, cost, stock; min margin per
category; max discount). Replace them with the official starter-kit files
before submission runs -- the agent reads whatever is in data/.
"""
import csv
import json
import random
from pathlib import Path

HERE = Path(__file__).parent
random.seed(7)

CATEGORIES = {
    # category: (price range in INR, cost ratio range, items)
    "electronics": ((1500, 25000), (0.70, 0.85), [
        "Wireless Earbuds", "Bluetooth Speaker", "Smart Watch", "Power Bank 20000mAh",
        "USB-C Hub", "Mechanical Keyboard", "Wireless Mouse", "Webcam 1080p",
        "Noise Cancelling Headphones", "Portable SSD 1TB", "Fitness Band", "Action Camera",
        "Smart Plug", "LED Desk Lamp", "Router AX1800"]),
    "apparel": ((400, 4000), (0.35, 0.55), [
        "Running Shoes", "Cotton T-Shirt", "Denim Jacket", "Track Pants", "Hoodie",
        "Formal Shirt", "Kurta", "Sports Socks (3 pack)", "Rain Jacket", "Cap",
        "Leather Belt", "Sneakers", "Sandals", "Polo T-Shirt", "Windcheater"]),
    "home": ((300, 8000), (0.45, 0.65), [
        "Steel Water Bottle", "Non-stick Pan", "Pressure Cooker 5L", "Bedsheet Set",
        "Cushion Covers (5)", "Wall Clock", "Table Lamp", "Storage Box Set", "Dinner Set",
        "Electric Kettle", "Mixer Grinder", "Curtains (2)", "Doormat", "Lunch Box", "Bath Towel Set"]),
    "books": ((150, 1200), (0.55, 0.75), [
        "Python Crash Course", "Atomic Habits", "The Psychology of Money", "Clean Code",
        "Deep Work", "Sapiens", "Ikigai", "Wings of Fire", "Designing Data-Intensive Applications",
        "The Alchemist", "Rich Dad Poor Dad", "Thinking Fast and Slow"]),
    "sports": ((300, 9000), (0.50, 0.70), [
        "Yoga Mat", "Cricket Bat", "Football", "Badminton Racket", "Dumbbell Set 10kg",
        "Skipping Rope", "Cycling Helmet", "Tennis Balls (3)", "Resistance Bands",
        "Gym Bag", "Table Tennis Set", "Shuttlecocks (6)"]),
    "beauty": ((150, 2500), (0.30, 0.50), [
        "Face Wash", "Sunscreen SPF50", "Hair Dryer", "Beard Trimmer", "Moisturiser",
        "Lip Balm Pack", "Shampoo 650ml", "Perfume 100ml", "Hair Straightener",
        "Aloe Vera Gel", "Body Lotion", "Face Serum"]),
    "grocery": ((80, 1500), (0.75, 0.90), [
        "Basmati Rice 5kg", "Cold Pressed Groundnut Oil 1L", "Almonds 500g", "Green Tea (100 bags)",
        "Dark Chocolate Pack", "Organic Honey 500g", "Coffee Beans 250g", "Dry Fruit Mix 1kg",
        "Masala Chai Mix", "Peanut Butter 1kg"]),
}

POLICY = {
    "min_margin": {  # minimum margin per category
        "electronics": 0.08, "apparel": 0.25, "home": 0.18, "books": 0.12,
        "sports": 0.18, "beauty": 0.25, "grocery": 0.06,
    },
    "max_discount": 0.25,  # never more than 25% off list price
}


def main():
    rows = []
    n = 1
    for cat, ((lo, hi), (clo, chi), names) in CATEGORIES.items():
        for name in names:
            price = round(random.uniform(lo, hi) / 10) * 10 - 1  # e.g. 2499
            cost = round(price * random.uniform(clo, chi), 2)
            stock = random.choice([0, 1, 2, 3, 5, 8, 12, 20, 35, 50]) if random.random() > 0.06 else 0
            rows.append({"sku": f"P{n:03d}", "name": name, "category": cat,
                         "price": price, "cost": cost, "stock": stock})
            n += 1
    with open(HERE / "store.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["sku", "name", "category", "price", "cost", "stock"])
        w.writeheader()
        w.writerows(rows)
    with open(HERE / "policy.json", "w") as f:
        json.dump(POLICY, f, indent=2)
    print(f"wrote {len(rows)} products")


if __name__ == "__main__":
    main()
