#!/usr/bin/env python3
"""
Seed 2 Tenants (Electronics Store + Fashion Store) with Products, Categories,
FAQ, Policies, and Bundle Discount configs for comprehensive testing.
"""

import asyncio
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_2_tenants")

# ─── TENANT CONFIG ───
TENANTS = {
    "store_elec_002": {
        "name": "TechPro Electronics",
        "org_id": "org_elec_002",
        "currency": "USD",
        "language": "en",
        "description": "Premium electronics and computer accessories store",
    },
    "store_fashion_001": {
        "name": "StyleHub Fashion",
        "org_id": "org_fashion_001",
        "currency": "USD",
        "language": "en",
        "description": "Trendy fashion and accessories boutique",
    },
}

# ─── TENANT A: ELECTRONICS STORE ───
ELECTRONICS_PRODUCTS = [
    {
        "external_id": "prod_elec_001",
        "title": "MacBook Pro 16-inch M3 Max",
        "description": "Apple MacBook Pro with M3 Max chip, 36GB RAM, 1TB SSD, 16-inch Liquid Retina XDR display",
        "price": 3499.99,
        "sku": "MBP-M3-16-36-1TB",
        "category": "Laptops",
        "brand": "Apple",
        "inventory_quantity": 15,
        "specs": {"cpu": "M3 Max 16-core", "ram": "36GB", "storage": "1TB SSD", "display": "16-inch Liquid Retina XDR"},
        "max_discount_pct": 10.0,
        "image_url": "https://store.example.com/mbp16.jpg",
    },
    {
        "external_id": "prod_elec_002",
        "title": "Dell XPS 15 OLED",
        "description": "Dell XPS 15 with Intel Core i9-13900H, 32GB RAM, 1TB SSD, 15.6-inch OLED display",
        "price": 2499.99,
        "sku": "DEL-XPS-15-i9-32-1TB",
        "category": "Laptops",
        "brand": "Dell",
        "inventory_quantity": 23,
        "specs": {"cpu": "Intel Core i9-13900H", "ram": "32GB", "storage": "1TB SSD", "display": "15.6-inch OLED"},
        "max_discount_pct": 15.0,
        "image_url": "https://store.example.com/xps15.jpg",
    },
    {
        "external_id": "prod_elec_003",
        "title": "LG 27-inch 4K Monitor",
        "description": "LG 27UP850N 27-inch 4K UHD IPS Monitor with USB-C 96W PD, HDMI, DisplayPort",
        "price": 499.99,
        "sku": "LG-27UP850N",
        "category": "Monitors",
        "brand": "LG",
        "inventory_quantity": 34,
        "specs": {"resolution": "3840x2160", "panel": "IPS", "size": "27-inch", "ports": "USB-C 96W PD, HDMI, DP"},
        "max_discount_pct": 12.0,
        "image_url": "https://store.example.com/lg27.jpg",
    },
    {
        "external_id": "prod_elec_004",
        "title": "Monitor Arm Stand",
        "description": "Ergonomic single monitor desk mount arm, fits 17-32 inch screens, VESA compatible, gas spring adjustable",
        "price": 79.99,
        "sku": "MNT-ARM-001",
        "category": "Monitors",
        "brand": "ErgoPro",
        "inventory_quantity": 60,
        "specs": {"type": "Gas Spring", "size_range": "17-32 inch", "vesa": "75x75, 100x100", "weight_capacity": "8kg"},
        "max_discount_pct": 20.0,
        "image_url": "https://store.example.com/monitor-arm.jpg",
    },
    {
        "external_id": "prod_elec_005",
        "title": "Logitech MX Mechanical Keyboard",
        "description": "Logitech MX Mechanical Wireless Keyboard with Tactile Switches, Full-size, Bluetooth + USB-C",
        "price": 149.99,
        "sku": "LOG-MX-MECH",
        "category": "Accessories",
        "brand": "Logitech",
        "inventory_quantity": 120,
        "specs": {
            "type": "Mechanical",
            "switches": "Tactile",
            "layout": "Full-size",
            "connectivity": "Bluetooth + USB-C",
        },
        "max_discount_pct": 15.0,
        "image_url": "https://store.example.com/mx-mech.jpg",
    },
    {
        "external_id": "prod_elec_006",
        "title": "Logitech MX Master 3S Mouse",
        "description": "Logitech MX Master 3S Wireless Performance Mouse with 8K DPI, Quiet Clicks, USB-C",
        "price": 99.99,
        "sku": "LOG-MX-MASTER-3S",
        "category": "Accessories",
        "brand": "Logitech",
        "inventory_quantity": 88,
        "specs": {"type": "Performance", "dpi": "8000", "connectivity": "Bluetooth + USB-C", "battery": "70 days"},
        "max_discount_pct": 10.0,
        "image_url": "https://store.example.com/mx-master3s.jpg",
    },
    {
        "external_id": "prod_elec_007",
        "title": "Sony WH-1000XM5 Headphones",
        "description": "Sony WH-1000XM5 Wireless Noise Cancelling Headphones, 30h battery, Adaptive ANC",
        "price": 349.99,
        "sku": "SONY-WH1000XM5",
        "category": "Audio",
        "brand": "Sony",
        "inventory_quantity": 78,
        "specs": {
            "type": "Over-ear",
            "battery": "30 hours",
            "noise_cancelling": "Adaptive",
            "connectivity": "Bluetooth 5.2",
        },
        "max_discount_pct": 10.0,
        "image_url": "https://store.example.com/wh1000xm5.jpg",
    },
    {
        "external_id": "prod_elec_008",
        "title": "Apple AirPods Pro 2nd Gen",
        "description": "Apple AirPods Pro 2nd Generation with USB-C, Adaptive Audio, H2 Chip",
        "price": 249.99,
        "sku": "AP-AIRPODS-PRO-2",
        "category": "Audio",
        "brand": "Apple",
        "inventory_quantity": 95,
        "specs": {"type": "In-ear", "chip": "H2", "anc": "Adaptive", "connectivity": "Bluetooth 5.3"},
        "max_discount_pct": 5.0,
        "image_url": "https://store.example.com/airpods-pro2.jpg",
    },
    {
        "external_id": "prod_elec_009",
        "title": "Phone Stand Adjustable",
        "description": "Adjustable aluminum phone stand for cooking/desk use, 360° rotation, fits all phones up to 7 inch",
        "price": 24.99,
        "sku": "PH-STAND-001",
        "category": "Accessories",
        "brand": "DesiCo",
        "inventory_quantity": 200,
        "specs": {
            "material": "Aluminum",
            "rotation": "360°",
            "compatibility": "4-7 inch phones",
            "use_case": "Desk, Kitchen, Bedside",
        },
        "max_discount_pct": 25.0,
        "image_url": "https://store.example.com/phone-stand.jpg",
    },
    {
        "external_id": "prod_elec_010",
        "title": "ASUS RTX 4080 Graphics Card",
        "description": "ASUS ROG Strix GeForce RTX 4080 16GB GDDR6X Graphics Card, PCIe 4.0",
        "price": 1199.99,
        "sku": "ASUS-RTX4080-16G",
        "category": "Components",
        "brand": "ASUS",
        "inventory_quantity": 8,
        "specs": {"gpu": "RTX 4080", "vram": "16GB GDDR6X", "interface": "PCIe 4.0", "ports": "HDMI 2.1 + DP 1.4a"},
        "max_discount_pct": 8.0,
        "image_url": "https://store.example.com/rtx4080.jpg",
    },
]

ELECTRONICS_CATEGORIES = [
    {"external_id": "cat_elec_001", "name": "Laptops", "description": "Laptop computers and notebooks"},
    {
        "external_id": "cat_elec_002",
        "name": "Monitors",
        "description": "Computer monitors and displays, including monitor arms and stands",
    },
    {
        "external_id": "cat_elec_003",
        "name": "Accessories",
        "description": "Computer peripherals, keyboards, mice, phone stands, and accessories",
    },
    {"external_id": "cat_elec_004", "name": "Audio", "description": "Headphones, earphones, and audio equipment"},
    {"external_id": "cat_elec_005", "name": "Components", "description": "PC components and hardware"},
]

# ─── TENANT B: FASHION STORE ───
FASHION_PRODUCTS = [
    {
        "external_id": "prod_fash_001",
        "title": "Classic Leather Jacket",
        "description": "Premium genuine leather jacket, slim fit, with quilted lining and YKK zippers",
        "price": 299.99,
        "sku": "FASH-LJ-001",
        "category": "Outerwear",
        "brand": "UrbanEdge",
        "inventory_quantity": 25,
        "specs": {"material": "Genuine Leather", "fit": "Slim", "lining": "Quilted Polyester", "closure": "YKK Zipper"},
        "max_discount_pct": 15.0,
        "image_url": "https://store.example.com/leather-jacket.jpg",
    },
    {
        "external_id": "prod_fash_002",
        "title": "Designer Denim Jeans",
        "description": "Slim-fit designer denim jeans, stretch cotton blend, 5-pocket styling",
        "price": 89.99,
        "sku": "FASH-DJ-001",
        "category": "Bottoms",
        "brand": "UrbanEdge",
        "inventory_quantity": 80,
        "specs": {"material": "98% Cotton, 2% Elastane", "fit": "Slim", "rise": "Mid", "length": "Regular"},
        "max_discount_pct": 20.0,
        "image_url": "https://store.example.com/denim-jeans.jpg",
    },
    {
        "external_id": "prod_fash_003",
        "title": "Merino Wool Sweater",
        "description": "Lightweight merino wool crew neck sweater, machine washable, perfect for layering",
        "price": 129.99,
        "sku": "FASH-MW-001",
        "category": "Tops",
        "brand": "CozyLuxe",
        "inventory_quantity": 50,
        "specs": {"material": "100% Merino Wool", "care": "Machine Washable", "fit": "Regular", "neck": "Crew"},
        "max_discount_pct": 15.0,
        "image_url": "https://store.example.com/merino-sweater.jpg",
    },
    {
        "external_id": "prod_fash_004",
        "title": "Cashmere Scarf",
        "description": "Luxurious pure cashmere scarf, 180cm x 70cm, fringed edges, available in 12 colors",
        "price": 79.99,
        "sku": "FASH-CS-001",
        "category": "Accessories",
        "brand": "CozyLuxe",
        "inventory_quantity": 100,
        "specs": {"material": "100% Cashmere", "size": "180x70 cm", "care": "Dry Clean Only", "style": "Fringed"},
        "max_discount_pct": 10.0,
        "image_url": "https://store.example.com/cashmere-scarf.jpg",
    },
    {
        "external_id": "prod_fash_005",
        "title": "Leather Crossbody Bag",
        "description": "Handcrafted genuine leather crossbody bag with adjustable strap, multiple compartments",
        "price": 159.99,
        "sku": "FASH-CB-001",
        "category": "Bags",
        "brand": "UrbanEdge",
        "inventory_quantity": 35,
        "specs": {
            "material": "Genuine Leather",
            "strap": "Adjustable 120cm",
            "compartments": "3 Internal + 1 Zip",
            "closure": "Magnetic Snap",
        },
        "max_discount_pct": 12.0,
        "image_url": "https://store.example.com/crossbody-bag.jpg",
    },
    {
        "external_id": "prod_fash_006",
        "title": "Silk Evening Dress",
        "description": "Elegant silk evening dress, floor-length, with V-neckline and concealed side zip",
        "price": 249.99,
        "sku": "FASH-SD-001",
        "category": "Dresses",
        "brand": "EleganceStudio",
        "inventory_quantity": 15,
        "specs": {
            "material": "100% Silk",
            "length": "Floor-length",
            "neckline": "V-Neck",
            "closure": "Concealed Side Zip",
        },
        "max_discount_pct": 10.0,
        "image_url": "https://store.example.com/silk-dress.jpg",
    },
    {
        "external_id": "prod_fash_007",
        "title": "Running Sneakers",
        "description": "Lightweight running sneakers with responsive cushioning, breathable mesh upper",
        "price": 119.99,
        "sku": "FASH-RS-001",
        "category": "Footwear",
        "brand": "StepFit",
        "inventory_quantity": 60,
        "specs": {"upper": "Breathable Mesh", "sole": "Rubber", "cushioning": "EVA Foam", "closure": "Lace-up"},
        "max_discount_pct": 20.0,
        "image_url": "https://store.example.com/running-sneakers.jpg",
    },
    {
        "external_id": "prod_fash_008",
        "title": "Leather Ankle Boots",
        "description": "Classic leather ankle boots with side zip, block heel, cushioned insole",
        "price": 179.99,
        "sku": "FASH-LB-001",
        "category": "Footwear",
        "brand": "UrbanEdge",
        "inventory_quantity": 40,
        "specs": {
            "material": "Genuine Leather",
            "heel": "Block 4cm",
            "closure": "Side Zipper",
            "sole": "Leather + Rubber",
        },
        "max_discount_pct": 15.0,
        "image_url": "https://store.example.com/ankle-boots.jpg",
    },
    {
        "external_id": "prod_fash_009",
        "title": "Leather Belt",
        "description": "Italian leather belt with brushed buckle, 3.5cm width, reversible design",
        "price": 59.99,
        "sku": "FASH-LBT-001",
        "category": "Accessories",
        "brand": "UrbanEdge",
        "inventory_quantity": 120,
        "specs": {
            "material": "Italian Leather",
            "width": "3.5cm",
            "buckle": "Brushed Metal",
            "design": "Reversible Black/Brown",
        },
        "max_discount_pct": 10.0,
        "image_url": "https://store.example.com/leather-belt.jpg",
    },
    {
        "external_id": "prod_fash_010",
        "title": "Aviator Sunglasses",
        "description": "Classic aviator sunglasses with polarized lenses, gold frame, UV400 protection",
        "price": 149.99,
        "sku": "FASH-AS-001",
        "category": "Accessories",
        "brand": "EleganceStudio",
        "inventory_quantity": 75,
        "specs": {"frame": "Gold Metal", "lens": "Polarized Green", "protection": "UV400", "style": "Aviator"},
        "max_discount_pct": 15.0,
        "image_url": "https://store.example.com/aviators.jpg",
    },
]

FASHION_CATEGORIES = [
    {"external_id": "cat_fash_001", "name": "Outerwear", "description": "Jackets, coats, and outerwear"},
    {"external_id": "cat_fash_002", "name": "Tops", "description": "Shirts, blouses, sweaters, and tops"},
    {"external_id": "cat_fash_003", "name": "Bottoms", "description": "Jeans, pants, skirts, and shorts"},
    {"external_id": "cat_fash_004", "name": "Dresses", "description": "Evening, casual, and formal dresses"},
    {"external_id": "cat_fash_005", "name": "Footwear", "description": "Shoes, boots, sneakers, and sandals"},
    {"external_id": "cat_fash_006", "name": "Bags", "description": "Handbags, crossbody bags, and backpacks"},
    {
        "external_id": "cat_fash_007",
        "name": "Accessories",
        "description": "Scarves, belts, sunglasses, hats, and jewelry",
    },
]

# ─── SHARED FAQ & POLICY (per tenant) ───
FAQ_ENTRIES = [
    {
        "external_id": "faq_001",
        "question": "What is your return policy?",
        "answer": "We accept returns within 30 days of purchase. Items must be unused and in original packaging. Refunds are processed within 5-7 business days after we receive the item.",
    },
    {
        "external_id": "faq_002",
        "question": "How long does shipping take?",
        "answer": "Standard shipping takes 3-5 business days within the continental US. Express shipping takes 1-2 business days. International shipping takes 7-14 business days. Free shipping on orders over $50.",
    },
    {
        "external_id": "faq_003",
        "question": "What is your warranty policy?",
        "answer": "All products come with a 1-year manufacturer warranty. Extended warranty plans are available for purchase within 30 days. Covers manufacturing defects but not accidental damage.",
    },
    {
        "external_id": "faq_004",
        "question": "Do you offer price matching?",
        "answer": "Yes, we offer price matching within 14 days of purchase. If you find a lower price from an authorized retailer, we will refund the difference.",
    },
    {
        "external_id": "faq_005",
        "question": "How do I track my order?",
        "answer": "Once your order ships, you will receive a tracking number via email. You can track your order on our website.",
    },
    {
        "external_id": "faq_006",
        "question": "Can I cancel or change my order?",
        "answer": "Orders can be canceled or modified within 1 hour of placement. After that, the order enters processing and cannot be changed.",
    },
    {
        "external_id": "faq_007",
        "question": "What payment methods do you accept?",
        "answer": "We accept Visa, Mastercard, American Express, PayPal, and Apple Pay. All payments are processed securely.",
    },
    {
        "external_id": "faq_008",
        "question": "How can I contact customer support?",
        "answer": "You can contact customer support via email at support@store.com, phone at 1-800-STORE, or live chat on our website. Hours: Mon-Fri 9AM-6PM EST.",
    },
]

POLICY_ENTRIES = [
    {
        "external_id": "policy_001",
        "title": "Refund Policy",
        "content": "Full refunds are issued for items returned within 30 days in original condition. Partial refunds may be issued for opened items. Refund processing takes 5-7 business days. Refunds are issued to the original payment method.",
    },
    {
        "external_id": "policy_002",
        "title": "Privacy Policy",
        "content": "We collect only necessary personal information for order processing and shipping. We do not share customer data with third parties except shipping carriers. Customer data is encrypted and stored securely. You may request data deletion at any time.",
    },
    {
        "external_id": "policy_003",
        "title": "Terms of Service",
        "content": "By using our store, you agree to these terms. All prices are in USD and subject to change. We reserve the right to cancel orders due to pricing errors. Products are sold as described. Our liability is limited to the purchase price.",
    },
    {
        "external_id": "policy_004",
        "title": "Customer Support Policy",
        "content": "Our customer support team is available Monday-Friday 9AM-6PM EST. We aim to respond to all inquiries within 24 hours. For urgent issues, please call our support line. We are committed to resolving your concerns promptly and fairly.",
    },
    {
        "external_id": "policy_005",
        "title": "Shipping Policy",
        "content": "We ship to all 50 US states and 30+ international countries. Standard shipping (3-5 business days) is free on orders over $50. Express shipping (1-2 business days) is $12.99. International shipping rates vary by destination.",
    },
]


async def seed_tenant(store_id: str, config: dict):
    from app.infrastructure.mongodb.client import MongoClientManager
    from app.infrastructure.mongodb.collections import get_entities_collection

    await MongoClientManager.connect()
    collection = get_entities_collection()

    now = datetime.now(UTC)
    org_id = config["org_id"]
    store_name = config["name"]
    total = 0

    del_result = await collection.delete_many({"store_id": store_id})
    logger.info("  Cleaned %d old entities for %s (%s)", del_result.deleted_count, store_id, store_name)

    is_elec = "elec" in store_id
    products = ELECTRONICS_PRODUCTS if is_elec else FASHION_PRODUCTS
    categories = ELECTRONICS_CATEGORIES if is_elec else FASHION_CATEGORIES

    for p in products:
        eid = p["external_id"]
        data = {k: v for k, v in p.items() if k not in ("external_id", "entity_type")}
        await collection.update_one(
            {"store_id": store_id, "external_id": eid, "entity_type": "product"},
            {
                "$set": {
                    "store_id": store_id,
                    "organization_id": org_id,
                    "entity_type": "product",
                    "external_id": eid,
                    "data": data,
                    "synced_at": now,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        total += 1
    logger.info("  [PASS] Seeded %d products for %s", len(products), store_name)

    for c in categories:
        eid = c["external_id"]
        data = {k: v for k, v in c.items() if k not in ("external_id",)}
        await collection.update_one(
            {"store_id": store_id, "external_id": eid, "entity_type": "category"},
            {
                "$set": {
                    "store_id": store_id,
                    "organization_id": org_id,
                    "entity_type": "category",
                    "external_id": eid,
                    "data": data,
                    "synced_at": now,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        total += 1
    logger.info("  [PASS] Seeded %d categories for %s", len(categories), store_name)

    for faq in FAQ_ENTRIES:
        eid = faq["external_id"]
        data = {k: v for k, v in faq.items() if k not in ("external_id", "entity_type")}
        await collection.update_one(
            {"store_id": store_id, "external_id": eid, "entity_type": "faq"},
            {
                "$set": {
                    "store_id": store_id,
                    "organization_id": org_id,
                    "entity_type": "faq",
                    "external_id": eid,
                    "data": data,
                    "synced_at": now,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        total += 1
    logger.info("  [PASS] Seeded %d FAQ entries for %s", len(FAQ_ENTRIES), store_name)

    for pol in POLICY_ENTRIES:
        eid = pol["external_id"]
        data = {k: v for k, v in pol.items() if k not in ("external_id", "entity_type")}
        await collection.update_one(
            {"store_id": store_id, "external_id": eid, "entity_type": "policy"},
            {
                "$set": {
                    "store_id": store_id,
                    "organization_id": org_id,
                    "entity_type": "policy",
                    "external_id": eid,
                    "data": data,
                    "synced_at": now,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        total += 1
    logger.info("  [PASS] Seeded %d policy entries for %s", len(POLICY_ENTRIES), store_name)

    MongoClientManager.disconnect()
    logger.info("  Total seeded for %s: %d entities", store_name, total)
    return total


async def main():
    print("\n" + "=" * 72)
    print("  SEED 2 TENANTS: Electronics + Fashion Stores")
    print("=" * 72)

    for store_id, config in TENANTS.items():
        try:
            count = await seed_tenant(store_id, config)
            print(f"  [PASS] {config['name']} ({store_id}) — {count} entities seeded")
        except Exception as e:
            print(f"  [FAIL] {config['name']} ({store_id}): {e}")

    print("=" * 72)
    print("  SEEDING COMPLETE")
    print("  Tenants: store_elec_002 (TechPro Electronics), store_fashion_001 (StyleHub Fashion)")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
