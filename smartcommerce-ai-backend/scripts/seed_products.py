"""Seed sample products and categories into the database."""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import async_session_maker
from app.models import Category, Product, User, UserRole
from app.core.security import hash_password


CATEGORIES = [
    {"name": "Electronics", "slug": "electronics", "description": "Gadgets, devices, and accessories"},
    {"name": "Clothing", "slug": "clothing", "description": "Fashion and apparel"},
    {"name": "Home & Kitchen", "slug": "home-kitchen", "description": "Home essentials and kitchen tools"},
    {"name": "Books", "slug": "books", "description": "Books across all genres"},
    {"name": "Sports & Outdoors", "slug": "sports-outdoors", "description": "Sports equipment and outdoor gear"},
]

PRODUCTS = [
    # Electronics
    {"name": "MacBook Pro 14\"", "slug": "macbook-pro-14", "description": "Apple M3 Pro chip, 18GB RAM, 512GB SSD. Perfect for developers and creatives.", "price": 1999.00, "stock": 15, "category_slug": "electronics", "image_url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=400"},
    {"name": "Sony WH-1000XM5", "slug": "sony-wh-1000xm5", "description": "Industry-leading noise cancellation wireless headphones.", "price": 349.99, "stock": 30, "category_slug": "electronics", "image_url": "https://images.unsplash.com/photo-1618366712010-f4ae9c647dcb?w=400"},
    {"name": "iPhone 15 Pro", "slug": "iphone-15-pro", "description": "A17 Pro chip, titanium design, 48MP camera system.", "price": 999.00, "stock": 25, "category_slug": "electronics", "image_url": "https://images.unsplash.com/photo-1592750475338-74b7b21085ab?w=400"},
    {"name": "Samsung 4K Smart TV 55\"", "slug": "samsung-4k-tv-55", "description": "Crystal UHD display with HDR and smart features.", "price": 549.99, "stock": 10, "category_slug": "electronics", "image_url": "https://images.unsplash.com/photo-1593359677879-a4bb92f829d1?w=400"},
    {"name": "AirPods Pro 2", "slug": "airpods-pro-2", "description": "Active noise cancellation, spatial audio, MagSafe case.", "price": 249.00, "stock": 50, "category_slug": "electronics", "image_url": "https://images.unsplash.com/photo-1600294037681-c80b4cb5b434?w=400"},
    
    # Clothing
    {"name": "Classic Denim Jacket", "slug": "classic-denim-jacket", "description": "Timeless denim jacket with button closure and chest pockets.", "price": 89.99, "stock": 40, "category_slug": "clothing", "image_url": "https://images.unsplash.com/photo-1576995853123-5a10305d93c0?w=400"},
    {"name": "Premium Cotton T-Shirt", "slug": "premium-cotton-tshirt", "description": "Soft 100% organic cotton, available in multiple colors.", "price": 29.99, "stock": 100, "category_slug": "clothing", "image_url": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400"},
    {"name": "Running Sneakers", "slug": "running-sneakers", "description": "Lightweight with responsive cushioning for daily runs.", "price": 129.99, "stock": 35, "category_slug": "clothing", "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=400"},
    
    # Home & Kitchen
    {"name": "Instant Pot Duo 7-in-1", "slug": "instant-pot-duo", "description": "Electric pressure cooker, slow cooker, rice cooker, and more.", "price": 89.95, "stock": 20, "category_slug": "home-kitchen", "image_url": "https://images.unsplash.com/photo-1585515320310-259814833e62?w=400"},
    {"name": "Dyson V15 Detect", "slug": "dyson-v15-detect", "description": "Cordless vacuum with laser dust detection and LCD screen.", "price": 749.99, "stock": 8, "category_slug": "home-kitchen", "image_url": "https://images.unsplash.com/photo-1558317374-067fb5f30001?w=400"},
    {"name": "KitchenAid Stand Mixer", "slug": "kitchenaid-stand-mixer", "description": "5-quart tilt-head stand mixer with 10 speeds.", "price": 449.99, "stock": 12, "category_slug": "home-kitchen", "image_url": "https://images.unsplash.com/photo-1594385208974-2e75f8d7bb48?w=400"},
    
    # Books  
    {"name": "Clean Code", "slug": "clean-code", "description": "A Handbook of Agile Software Craftsmanship by Robert C. Martin.", "price": 39.99, "stock": 50, "category_slug": "books", "image_url": "https://images.unsplash.com/photo-1532012197267-da84d127e765?w=400"},
    {"name": "Atomic Habits", "slug": "atomic-habits", "description": "An Easy & Proven Way to Build Good Habits by James Clear.", "price": 16.99, "stock": 75, "category_slug": "books", "image_url": "https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=400"},
    
    # Sports & Outdoors
    {"name": "Yoga Mat Premium", "slug": "yoga-mat-premium", "description": "6mm thick, non-slip surface, eco-friendly materials.", "price": 49.99, "stock": 60, "category_slug": "sports-outdoors", "image_url": "https://images.unsplash.com/photo-1601925260368-ae2f83cf8b7f?w=400"},
    {"name": "Camping Tent 4-Person", "slug": "camping-tent-4person", "description": "Waterproof, easy setup, with rainfly and mesh windows.", "price": 199.99, "stock": 15, "category_slug": "sports-outdoors", "image_url": "https://images.unsplash.com/photo-1504280390367-361c6d9f38f4?w=400"},
]


async def seed_database():
    """Seed the database with sample data."""
    async with async_session_maker() as session:
        try:
            # Create admin user
            admin = User(
                email="admin@smartcommerce.ai",
                username="admin",
                password_hash=hash_password(os.environ.get("ADMIN_PASSWORD", "admin123")),
                full_name="Admin User",
                role=UserRole.ADMIN,
            )
            session.add(admin)
            
            # Create test customer
            customer = User(
                email="customer@example.com",
                username="testuser",
                password_hash=hash_password("password123"),
                full_name="Test Customer",
                role=UserRole.CUSTOMER,
            )
            session.add(customer)
            
            # Create categories
            category_map = {}
            for cat_data in CATEGORIES:
                category = Category(**cat_data)
                session.add(category)
                category_map[cat_data["slug"]] = category
            
            await session.flush()
            
            # Create products
            for prod_data in PRODUCTS:
                prod_data = dict(prod_data)
                category_slug = prod_data.pop("category_slug")
                category = category_map.get(category_slug)
                product = Product(
                    **prod_data,
                    category_id=category.id if category else None,
                )
                session.add(product)
            
            await session.commit()
            print("✅ Database seeded successfully!")
            print(f"   - Created {len(CATEGORIES)} categories")
            print(f"   - Created {len(PRODUCTS)} products")
            print(f"   - Created admin user (admin / ADMIN_PASSWORD or admin123)")
            print(f"   - Created test user (testuser / password123)")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Error seeding database: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(seed_database())
