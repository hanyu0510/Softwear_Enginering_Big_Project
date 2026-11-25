from app.modules.wardrobe.service import list_recommendation_candidates


def test_health_uses_common_envelope(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["code"] == 0
    assert response.json()["data"] == {"status": "ok"}
    assert response.json()["requestId"].startswith("req_")


def test_authentication_is_required(client):
    response = client.get("/api/v1/items")
    assert response.status_code == 401
    assert response.json()["code"] == 40101


def test_unknown_route_uses_common_error_envelope(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.json()["code"] == 40401
    assert response.json()["data"] is None
    assert response.json()["requestId"].startswith("req_")


def test_debug_identity_and_page_are_disabled_in_production(client, auth, settings):
    settings.app_env = "production"
    api_response = client.get("/api/v1/items", headers=auth())
    assert api_response.status_code == 401
    assert api_response.json()["code"] == 40101
    page_response = client.get("/debug/wardrobe")
    assert page_response.status_code == 404
    assert page_response.json()["code"] == 40401


def test_upload_rejects_fake_image(client, auth):
    response = client.post(
        "/api/v1/uploads/image",
        headers=auth(),
        files={"file": ("fake.jpg", b"not-an-image", "image/jpeg")},
    )
    assert response.status_code == 400
    assert response.json()["code"] == 40001


def test_transparent_palette_png_gets_clean_thumbnail(
    client, auth, transparent_palette_image_bytes
):
    response = client.post(
        "/api/v1/uploads/image",
        headers=auth(),
        files={"file": ("transparent.png", transparent_palette_image_bytes, "image/png")},
    )
    assert response.status_code == 200
    thumb = client.get(response.json()["data"]["thumbUrl"], headers=auth())
    assert thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/jpeg"


def test_manual_create_list_filter_and_pagination(client, auth, create_item):
    first = create_item()
    create_item(name="藏青外套", category="outerwear", color="藏青", season=["winter"])

    response = client.get(
        "/api/v1/items?category=tops&season=autumn&page=1&pageSize=1",
        headers=auth(),
    )
    data = response.json()["data"]
    assert response.status_code == 200
    assert data["total"] == 1
    assert data["list"][0]["id"] == first["id"]
    assert data["list"][0]["source"] == "manual"
    assert data["list"][0]["verify_status"] == "confirmed"

    keyword = client.get(
        "/api/v1/items?color=藏青&keyword=外套&page=1&pageSize=20", headers=auth()
    ).json()["data"]
    assert keyword["total"] == 1
    assert keyword["list"][0]["name"] == "藏青外套"


def test_all_categories_and_full_tag_enums_are_accepted(client, auth, create_item):
    categories = [
        "tops", "bottoms", "outerwear", "dress", "shoes", "bag", "accessory", "other"
    ]
    for index, category in enumerate(categories):
        create_item(
            name=f"category-{category}",
            category=category,
            season=["spring", "summer", "autumn", "winter"] if index == 0 else [],
            style=["minimal", "street", "sweet", "formal", "casual", "vintage", "sporty"] if index == 0 else [],
            occasion=["commute", "date", "travel", "casual", "formal", "party", "sport"] if index == 0 else [],
        )

    for category in categories:
        data = client.get(
            f"/api/v1/items?category={category}&page=1&pageSize=20", headers=auth()
        ).json()["data"]
        assert data["total"] == 1
        assert data["list"][0]["category"] == category


def test_real_pagination_has_stable_non_overlapping_pages(client, auth, create_item):
    for index in range(3):
        create_item(name=f"分页衣物-{index}")
    page_one = client.get("/api/v1/items?page=1&pageSize=2", headers=auth()).json()["data"]
    page_two = client.get("/api/v1/items?page=2&pageSize=2", headers=auth()).json()["data"]
    assert page_one["total"] == 3
    assert page_two["total"] == 3
    assert len(page_one["list"]) == 2
    assert len(page_two["list"]) == 1
    assert {item["id"] for item in page_one["list"]}.isdisjoint(
        {item["id"] for item in page_two["list"]}
    )


def test_invalid_enum_uses_contract_error(client, auth, upload_image):
    uploaded = upload_image()
    response = client.post(
        "/api/v1/items",
        headers=auth(),
        json={
            "name": "错误衣物",
            "category": "hat",
            "imageFileId": uploaded["fileId"],
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == 40001


def test_private_item_is_hidden_from_other_user(client, auth, create_item):
    item = create_item()
    response = client.get(f"/api/v1/items/{item['id']}", headers=auth("user_b"))
    assert response.status_code == 404
    assert response.json()["code"] == 40401

    forbidden_patch = client.patch(
        f"/api/v1/items/{item['id']}",
        headers=auth("user_b"),
        json={"name": "越权修改"},
    )
    assert forbidden_patch.status_code == 404


def test_user_cannot_claim_another_users_uploaded_file(client, auth, upload_image):
    uploaded = upload_image("user_a")
    response = client.post(
        "/api/v1/items",
        headers=auth("user_b"),
        json={"name": "越权图片", "category": "other", "imageFileId": uploaded["fileId"]},
    )
    assert response.status_code == 404
    assert response.json()["code"] == 40401


def test_public_item_and_media_are_readable_by_other_user(client, auth, create_item):
    item = create_item(visibility="public")
    response = client.get(f"/api/v1/items/{item['id']}", headers=auth("user_b"))
    assert response.status_code == 200
    media = client.get(item["thumb_url"], headers=auth("user_b"))
    assert media.status_code == 200
    assert media.headers["content-type"] == "image/jpeg"


def test_patch_only_changes_submitted_fields(client, auth, create_item):
    item = create_item()
    response = client.patch(
        f"/api/v1/items/{item['id']}",
        headers=auth(),
        json={"is_favorite": True, "color": "奶白"},
    )
    data = response.json()["data"]
    assert data["name"] == item["name"]
    assert data["category"] == item["category"]
    assert data["color"] == "奶白"
    assert data["is_favorite"] is True


def test_soft_delete_removes_item_from_list(client, auth, create_item):
    item = create_item()
    response = client.delete(f"/api/v1/items/{item['id']}", headers=auth())
    assert response.status_code == 200
    assert response.json()["code"] == 0
    listing = client.get("/api/v1/items", headers=auth()).json()["data"]
    assert listing["total"] == 0


def test_ai_mock_creates_pending_then_confirmed(client, auth, upload_image):
    uploaded = upload_image()
    response = client.post(
        "/api/v1/ai/recognize",
        headers=auth(),
        json={"imageFileId": uploaded["fileId"]},
    )
    assert response.status_code == 200
    recognized = response.json()["data"]
    assert recognized["verify_status"] == "pending"
    assert recognized["confidence"] == 0.2
    assert "category" in recognized["low_confidence_fields"]

    patched = client.patch(
        f"/api/v1/items/{recognized['id']}",
        headers=auth(),
        json={"name": "黑色夹克", "category": "outerwear", "color": "黑色"},
    )
    assert patched.status_code == 200
    confirmed = client.post(
        f"/api/v1/items/{recognized['id']}/confirm", headers=auth()
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["verify_status"] == "confirmed"

    repeated = client.post(
        f"/api/v1/items/{recognized['id']}/confirm", headers=auth()
    )
    assert repeated.status_code == 409
    assert repeated.json()["code"] == 40901


def test_failed_ai_can_be_retried_after_provider_recovers(
    client, auth, upload_image, settings
):
    settings.wardrobe_ai_provider = "disabled"
    uploaded = upload_image()
    failed = client.post(
        "/api/v1/ai/recognize",
        headers=auth(),
        json={"imageFileId": uploaded["fileId"]},
    )
    assert failed.status_code == 503
    failed_item = client.get("/api/v1/items", headers=auth()).json()["data"]["list"][0]
    assert failed_item["verify_status"] == "failed"

    settings.wardrobe_ai_provider = "mock"
    retried = client.post(
        f"/api/v1/ai/retry/{failed_item['id']}", headers=auth()
    )
    assert retried.status_code == 200
    assert retried.json()["data"]["verify_status"] == "pending"


def test_disabled_ai_records_failure_but_manual_flow_still_works(
    client, auth, upload_image, settings
):
    settings.wardrobe_ai_provider = "disabled"
    uploaded = upload_image()
    response = client.post(
        "/api/v1/ai/recognize",
        headers=auth(),
        json={"imageFileId": uploaded["fileId"]},
    )
    assert response.status_code == 503
    assert response.json()["code"] == 50002
    listing = client.get("/api/v1/items", headers=auth()).json()["data"]
    assert listing["list"][0]["verify_status"] == "failed"

    manual = client.post(
        "/api/v1/items",
        headers=auth(),
        json={
            "name": "识别失败后手动填写",
            "category": "other",
            "color": "米白",
            "imageFileId": uploaded["fileId"],
        },
    )
    assert manual.status_code == 201
    assert manual.json()["data"]["verify_status"] == "confirmed"
    after_fallback = client.get("/api/v1/items", headers=auth()).json()["data"]
    assert after_fallback["total"] == 1
    assert after_fallback["list"][0]["id"] == manual.json()["data"]["id"]


def test_wish_duplicate_availability_copy_and_candidates(
    client, auth, create_item, db_session, settings
):
    source = create_item(user="user_b", visibility="public", category="outerwear")
    response = client.post(
        "/api/v1/wish-items",
        headers=auth("user_a"),
        json={"source_item_id": source["id"]},
    )
    assert response.status_code == 201
    wish = response.json()["data"]
    assert wish["available"] is True

    duplicate = client.post(
        "/api/v1/wish-items",
        headers=auth("user_a"),
        json={"source_item_id": source["id"]},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == 40901

    candidates = list_recommendation_candidates(db_session, "user_a", "owned_and_wish")
    assert any(entry["source"] == "wish" for entry in candidates)

    copied = client.post(
        f"/api/v1/wish-items/{wish['id']}/copy-to-wardrobe",
        headers=auth("user_a"),
    )
    assert copied.status_code == 201
    assert copied.json()["data"]["source"] == "manual"
    assert copied.json()["data"]["visibility"] == "private"

    client.patch(
        f"/api/v1/items/{source['id']}",
        headers=auth("user_b"),
        json={"visibility": "private"},
    )
    wishes = client.get("/api/v1/wish-items", headers=auth("user_a")).json()["data"]
    assert wishes["list"][0]["available"] is False
    assert wishes["list"][0]["snapshot"]["image_url"] is None

    deleted = client.delete(
        f"/api/v1/wish-items/{wish['id']}", headers=auth("user_a")
    )
    assert deleted.status_code == 200
    assert client.get("/api/v1/wish-items", headers=auth("user_a")).json()["data"]["total"] == 0
