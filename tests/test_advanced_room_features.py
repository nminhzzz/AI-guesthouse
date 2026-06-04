import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.core.config import settings
from app.mongodb.documents.room_document import Room, RoomStatus, RoomType, Amenity, GenderType
from app.mongodb.documents.favorite_document import Favorite
from app.services.room_service import RoomService
from app.mysql.models.user_model import User, UserRole


async def run_tests():
    print("=== Initializing DB connection ===")
    client = AsyncIOMotorClient(settings.MONGO_URL)
    db = client[settings.MONGO_DB + "_test"] # Use a separate test db suffix to keep production clean
    await init_beanie(
        database=db,
        document_models=[Room, Favorite]
    )

    print("Cleaning up old test data...")
    await Room.find_all().delete()
    await Favorite.find_all().delete()

    # Define mock landlord User
    mock_owner = User(id=999, name="Test Owner", email="owner@test.com", role=UserRole.owner)

    print("=== Creating Test Rooms ===")
    # Room A: Female-only room in Q1, HCM. Price 3M, Area 25m2. WiFi.
    room_a = Room(
        title="Phòng trọ đẹp Quận 1 dành cho Nữ",
        description="Phòng trọ giá tốt, khu vực an ninh gần trường đại học...",
        room_type=RoomType.room,
        price=3000000,
        deposit=3000000,
        area=25.0,
        address="123 Nguyễn Thị Minh Khai",
        ward="Bến Thành",
        district="Quận 1",
        city="Hồ Chí Minh",
        max_people=2,
        gender=GenderType.female,
        amenities=[Amenity.wifi],
        owner_id=mock_owner.id,
        status=RoomStatus.active
    )
    await room_a.insert()

    # Room B: Mixed (all) apartment in Q3, HCM. Price 6M, Area 35m2. WiFi + Parking.
    room_b = Room(
        title="Căn hộ mini an ninh Quận 3",
        description="Chung cư mini cao cấp có hầm xe, bảo vệ 24/7...",
        room_type=RoomType.apartment,
        price=6000000,
        deposit=6000000,
        area=35.0,
        address="456 Nguyễn Đình Chiểu",
        ward="Phường 5",
        district="Quận 3",
        city="Hồ Chí Minh",
        max_people=3,
        gender=GenderType.all,
        amenities=[Amenity.wifi, Amenity.parking],
        owner_id=mock_owner.id,
        status=RoomStatus.active
    )
    await room_b.insert()

    # Room C: Male-only House in Q1, HCM. Price 12M, Area 70m2. Parking.
    room_c = Room(
        title="Nhà nguyên căn tiện nghi Quận 1 cho Nam",
        description="Cho thuê nhà nguyên căn làm văn phòng hoặc ở ghép cho Nam...",
        room_type=RoomType.house,
        price=12000000,
        deposit=12000000,
        area=70.0,
        address="789 Lê Lợi",
        ward="Bến Nghé",
        district="Quận 1",
        city="Hồ Chí Minh",
        max_people=6,
        gender=GenderType.male,
        amenities=[Amenity.parking],
        owner_id=mock_owner.id,
        status=RoomStatus.active
    )
    await room_c.insert()

    print(f"Created rooms. IDs: A={room_a.id}, B={room_b.id}, C={room_c.id}")

    # ==========================================
    # TEST 1: Advanced Filtering & Location
    # ==========================================
    print("\n--- Running Test 1: Advanced Filters ---")
    
    # 1.1 City/District Filter
    res = await RoomService.search_rooms(city="Hồ Chí Minh", district="Quận 1")
    assert len(res["items"]) == 2, f"Expected 2 rooms in District 1, HCM, got {len(res['items'])}"
    print("[OK] Location filter passed")

    # 1.2 Price Range Filter
    res = await RoomService.search_rooms(min_price=2000000, max_price=7000000)
    assert len(res["items"]) == 2, f"Expected 2 rooms between 2M and 7M, got {len(res['items'])}"
    print("[OK] Price filter passed")

    # 1.3 Area Range Filter
    res = await RoomService.search_rooms(min_area=30.0, max_area=80.0)
    assert len(res["items"]) == 2, f"Expected 2 rooms between 30 and 80 m2, got {len(res['items'])}"
    print("[OK] Area filter passed")

    # 1.4 Room Type Filter
    res = await RoomService.search_rooms(room_type=RoomType.house)
    assert len(res["items"]) == 1 and res["items"][0].id == room_c.id, "Expected only Room C (house)"
    print("[OK] Room type filter passed")

    # ==========================================
    # TEST 2: Smart Gender Match
    # ==========================================
    print("\n--- Running Test 2: Smart Gender Matching ---")
    
    # Female searching: Should match Room A (female-only) AND Room B (all gender)
    res = await RoomService.search_rooms(gender=GenderType.female)
    matched_ids = [r.id for r in res["items"]]
    assert room_a.id in matched_ids and room_b.id in matched_ids, f"Expected room A and B for female, got {matched_ids}"
    assert room_c.id not in matched_ids, "Should not return male-only room for female search"
    print("[OK] Female smart search matched A and B, excluded C")

    # Male searching: Should match Room C (male-only) AND Room B (all gender)
    res = await RoomService.search_rooms(gender=GenderType.male)
    matched_ids = [r.id for r in res["items"]]
    assert room_c.id in matched_ids and room_b.id in matched_ids, f"Expected room C and B for male, got {matched_ids}"
    assert room_a.id not in matched_ids, "Should not return female-only room for male search"
    print("[OK] Male smart search matched C and B, excluded A")

    # ==========================================
    # TEST 3: Amenities Filter (AND logic)
    # ==========================================
    print("\n--- Running Test 3: Amenities AND logic ---")
    
    # 3.1 WiFi only: Should match A and B
    res = await RoomService.search_rooms(amenities=[Amenity.wifi])
    matched_ids = [r.id for r in res["items"]]
    assert len(matched_ids) == 2 and room_a.id in matched_ids and room_b.id in matched_ids
    print("[OK] Wifi filter returned A and B")

    # 3.2 Wifi AND Parking: Should match ONLY B
    res = await RoomService.search_rooms(amenities=[Amenity.wifi, Amenity.parking])
    matched_ids = [r.id for r in res["items"]]
    assert len(matched_ids) == 1 and matched_ids[0] == room_b.id
    print("[OK] Wifi + Parking filter returned only B")

    # ==========================================
    # TEST 4: Sorting
    # ==========================================
    print("\n--- Running Test 4: Sorting ---")
    
    # Sort price asc: A (3M) -> B (6M) -> C (12M)
    res = await RoomService.search_rooms(sort_by="price", sort_order="asc")
    prices = [r.price for r in res["items"]]
    assert prices == [3000000, 6000000, 12000000], f"Expected sorted prices [3M, 6M, 12M], got {prices}"
    print("[OK] Sorting price ASC passed")

    # Sort price desc: C (12M) -> B (6M) -> A (3M)
    res = await RoomService.search_rooms(sort_by="price", sort_order="desc")
    prices = [r.price for r in res["items"]]
    assert prices == [12000000, 6000000, 3000000], f"Expected sorted prices [12M, 6M, 3M], got {prices}"
    print("[OK] Sorting price DESC passed")

    # Sort area desc: C (70) -> B (35) -> A (25)
    res = await RoomService.search_rooms(sort_by="area", sort_order="desc")
    areas = [r.area for r in res["items"]]
    assert areas == [70.0, 35.0, 25.0]
    print("[OK] Sorting area DESC passed")

    # ==========================================
    # TEST 5: Favorites (Toggle / List)
    # ==========================================
    print("\n--- Running Test 5: Favorites ---")
    
    # 5.1 Toggle Add favorite for user 100 on Room A
    res = await RoomService.toggle_favorite(room_id=str(room_a.id), current_user_id=100)
    assert res["is_favorite"] is True, "Expected favorite toggle to return True (added)"
    
    updated_room_a = await Room.get(room_a.id)
    assert updated_room_a.favorite_count == 1, "favorite_count should increment to 1"
    print("[OK] Added favorite correctly")

    # 5.2 Retrieve favorites list
    my_favs = await RoomService.get_my_favorites(current_user_id=100)
    assert len(my_favs["items"]) == 1 and my_favs["items"][0].id == room_a.id, "Expected user 100 favorites to contain Room A"
    print("[OK] Retrieved favorites list correctly")

    # 5.3 Toggle Remove favorite
    res = await RoomService.toggle_favorite(room_id=str(room_a.id), current_user_id=100)
    assert res["is_favorite"] is False, "Expected favorite toggle to return False (removed)"
    
    updated_room_a = await Room.get(room_a.id)
    assert updated_room_a.favorite_count == 0, "favorite_count should decrement to 0"
    
    my_favs = await RoomService.get_my_favorites(current_user_id=100)
    assert len(my_favs["items"]) == 0, "favorites list should now be empty"
    print("[OK] Removed favorite correctly")

    # ==========================================
    # TEST 6: Rented Status and Owner listings
    # ==========================================
    print("\n--- Running Test 6: Rented and Owner Listings ---")
    
    # 6.1 Owner marks Room A as rented
    await RoomService.mark_as_rented(room_id=str(room_a.id), current_user=mock_owner)
    
    # 6.2 Search should no longer return Room A since search only returns ACTIVE status
    res = await RoomService.search_rooms(city="Hồ Chí Minh")
    matched_ids = [r.id for r in res["items"]]
    assert room_a.id not in matched_ids, "Rented room should not be returned in public search"
    print("[OK] Rented room successfully hidden from public searches")

    # 6.3 Landlord profile should STILL show Room A (rented) and B, C (active)
    res = await RoomService.get_rooms_by_owner(owner_id=mock_owner.id)
    matched_ids = [r.id for r in res["items"]]
    assert len(matched_ids) == 3, f"Owner profile should return all active & rented listings. Got: {len(matched_ids)}"
    assert room_a.id in matched_ids, "Rented room should show on owner profile page"
    print("[OK] Landlord public profile list returns active + rented rooms")

    print("\n==========================================")
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("==========================================")


if __name__ == "__main__":
    asyncio.run(run_tests())
