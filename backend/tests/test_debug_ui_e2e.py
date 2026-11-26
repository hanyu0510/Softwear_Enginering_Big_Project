import re
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from playwright.sync_api import expect, sync_playwright

from app.core.config import get_settings
from app.core.db import get_db
from app.main import app


CHROME_PATHS = (
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def live_server(settings, db_session):
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    if not server.started:
        pytest.fail("测试服务器未能启动")
    try:
        yield f"http://127.0.0.1:{port}", settings
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        app.dependency_overrides.clear()


@pytest.fixture
def browser_page(live_server):
    base_url, settings = live_server
    executable = next((path for path in CHROME_PATHS if path.is_file()), None)
    if executable is None:
        pytest.skip("未找到 Chrome 或 Edge，无法执行浏览器端到端测试")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(executable),
            headless=True,
            args=["--disable-gpu"],
        )
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(f"{base_url}/debug/wardrobe", wait_until="networkidle")
        yield page, base_url, settings, errors
        browser.close()


def _api(base_url, method, path, user="user_a", **kwargs):
    with httpx.Client(base_url=base_url, timeout=10, trust_env=False) as client:
        return client.request(
            method,
            path,
            headers={"Authorization": f"Bearer dev:{user}"},
            **kwargs,
        )


def _upload(base_url, image_bytes, user="user_a"):
    response = _api(
        base_url,
        "POST",
        "/api/v1/uploads/image",
        user,
        files={"file": ("garment.jpg", image_bytes, "image/jpeg")},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["fileId"]


def _create_item(base_url, image_bytes, name, category, user="user_a", visibility="private"):
    file_id = _upload(base_url, image_bytes, user)
    response = _api(
        base_url,
        "POST",
        "/api/v1/items",
        user,
        json={
            "imageFileId": file_id,
            "name": name,
            "category": category,
            "color": "测试色",
            "warmth": 2,
            "season": ["spring"],
            "style": ["casual"],
            "occasion": ["casual"],
            "visibility": visibility,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_category_selection_and_card_category_are_really_clickable(browser_page, image_bytes):
    page, base_url, _, errors = browser_page
    _create_item(base_url, image_bytes, "上装点击测试", "tops")
    _create_item(base_url, image_bytes, "下装排除测试", "bottoms")
    page.locator("#loadItemsBtn").click()

    with page.expect_response(re.compile(r"/api/v1/items\?.*category=tops")):
        page.locator('#filterForm select[name="category"]').select_option("tops")
    expect(page.locator("#itemList .item-card")).to_have_count(1)
    expect(page.locator("#itemList")).to_contain_text("上装点击测试")
    expect(page.locator("#itemList")).not_to_contain_text("下装排除测试")

    with page.expect_response(re.compile(r"/api/v1/items\?")):
        page.locator('#filterForm select[name="category"]').select_option("")
    top_card = page.locator("#itemList .item-card").filter(has_text="上装点击测试")
    with page.expect_response(re.compile(r"/api/v1/items\?.*category=tops")):
        top_card.locator('[data-action="filter-category"]').click()
    expect(page.locator('#filterForm select[name="category"]')).to_have_value("tops")
    expect(page.locator("#itemList .item-card")).to_have_count(1)
    assert errors == []


def test_pagination_buttons_change_the_visible_page(browser_page, image_bytes):
    page, base_url, _, errors = browser_page
    for index in range(7):
        _create_item(base_url, image_bytes, f"分页衣物 {index}", "tops")
    page.locator("#loadItemsBtn").click()

    with page.expect_response(re.compile(r"pageSize=5")):
        page.locator('#filterForm select[name="pageSize"]').select_option("5")
    expect(page.locator("#itemList .item-card")).to_have_count(5)
    expect(page.locator("#nextPage")).to_be_enabled()
    first_page_ids = page.locator("#itemList .item-id").all_text_contents()

    with page.expect_response(re.compile(r"page=2&pageSize=5")):
        page.locator("#nextPage").click()
    expect(page.locator('#filterForm input[name="page"]')).to_have_value("2")
    expect(page.locator("#itemList .item-card")).to_have_count(2)
    second_page_ids = page.locator("#itemList .item-id").all_text_contents()
    assert set(first_page_ids).isdisjoint(second_page_ids)
    assert errors == []


def test_upload_create_edit_favorite_and_delete_from_the_page(browser_page, image_bytes):
    page, base_url, _, errors = browser_page
    page.locator("#imageInput").set_input_files(
        {"name": "shirt.jpg", "mimeType": "image/jpeg", "buffer": image_bytes}
    )
    with page.expect_response(re.compile(r"/api/v1/uploads/image$")):
        page.locator("#uploadBtn").click()
    expect(page.locator("#fileId")).not_to_have_value("")

    page.locator('#createForm input[name="name"]').fill("浏览器新增上装")
    page.locator('#createForm select[name="category"]').select_option("tops")
    with page.expect_response(re.compile(r"/api/v1/items$")):
        page.locator('#createForm button[type="submit"]').click()
    card = page.locator("#itemList .item-card").filter(has_text="浏览器新增上装")
    expect(card).to_have_count(1)

    with page.expect_response(re.compile(r"/api/v1/items/item_")):
        card.locator('[data-action="favorite"]').click()
    card = page.locator("#itemList .item-card").filter(has_text="浏览器新增上装")
    expect(card.locator('[data-action="favorite"]')).to_have_text("取消常用")

    card.locator('[data-action="edit"]').click()
    expect(page.locator("#editDialog")).to_be_visible()
    edit_form = page.locator("#editForm")
    edit_form.locator('[name="name"]').fill("浏览器编辑完成")
    edit_form.locator('[name="category"]').select_option("outerwear")
    edit_form.locator('[name="color"]').fill("深蓝色")
    edit_form.locator('[name="colors"]').fill("深蓝色, 银灰色")
    edit_form.locator('[name="warmth"]').select_option("4")
    edit_form.locator('[name="material"]').fill("羊毛混纺")
    edit_form.locator('[name="pattern"]').fill("细条纹")
    edit_form.locator('[name="season"]').select_option(["autumn", "winter"])
    edit_form.locator('[name="style"]').select_option(["minimal", "formal"])
    edit_form.locator('[name="occasion"]').select_option(["commute", "formal"])
    edit_form.locator('[name="visibility"]').select_option("public")
    edit_form.locator('[name="isFavorite"]').check()
    with page.expect_response(
        lambda response: response.request.method == "PATCH"
        and "/api/v1/items/item_" in response.url
    ):
        edit_form.locator('button[type="submit"]').click()
    edited_card = page.locator("#itemList .item-card").filter(has_text="浏览器编辑完成")
    expect(edited_card).to_contain_text("深蓝色")
    expect(edited_card).to_contain_text("羊毛混纺")
    expect(edited_card).to_contain_text("细条纹")
    expect(edited_card).to_contain_text("秋")
    expect(edited_card).to_contain_text("冬")
    expect(edited_card).to_contain_text("公开")
    item_id = edited_card.locator(".item-id").inner_text()
    saved_item = _api(base_url, "GET", f"/api/v1/items/{item_id}").json()["data"]
    assert saved_item["category"] == "outerwear"
    assert saved_item["colors"] == ["深蓝色", "银灰色"]
    assert saved_item["warmth"] == 4
    assert saved_item["material"] == "羊毛混纺"
    assert saved_item["pattern"] == "细条纹"
    assert saved_item["season"] == ["autumn", "winter"]
    assert saved_item["style"] == ["minimal", "formal"]
    assert saved_item["occasion"] == ["commute", "formal"]
    assert saved_item["visibility"] == "public"
    assert saved_item["is_favorite"] is True

    page.once("dialog", lambda dialog: dialog.accept())
    with page.expect_response(lambda response: response.request.method == "DELETE"):
        edited_card.locator('[data-action="delete"]').click()
    expect(page.locator("#itemList")).not_to_contain_text("浏览器编辑完成")
    assert errors == []


def test_ai_confirm_failure_retry_wish_copy_and_identity_switch(
    browser_page, image_bytes
):
    page, base_url, settings, errors = browser_page
    pending_file = _upload(base_url, image_bytes)
    pending_response = _api(
        base_url,
        "POST",
        "/api/v1/ai/recognize",
        json={"imageFileId": pending_file},
    )
    assert pending_response.status_code == 200
    pending_id = pending_response.json()["data"]["id"]

    settings.wardrobe_ai_provider = "disabled"
    failed_file = _upload(base_url, image_bytes)
    failed_response = _api(
        base_url,
        "POST",
        "/api/v1/ai/recognize",
        json={"imageFileId": failed_file},
    )
    assert failed_response.status_code == 503
    failed_items = _api(base_url, "GET", "/api/v1/items?page=1&pageSize=20").json()["data"]["list"]
    failed_id = next(item["id"] for item in failed_items if item["verify_status"] == "failed")
    settings.wardrobe_ai_provider = "mock"

    page.locator("#loadItemsBtn").click()
    pending_card = page.locator("#itemList .item-card").filter(has_text=pending_id)
    with page.expect_response(re.compile(fr"/items/{pending_id}/confirm")):
        pending_card.locator('[data-action="confirm"]').click()
    expect(page.locator("#itemList .item-card").filter(has_text=pending_id).locator(".badge")).to_have_text("confirmed")

    failed_card = page.locator("#itemList .item-card").filter(has_text=failed_id)
    with page.expect_response(re.compile(fr"/ai/retry/{failed_id}")):
        failed_card.locator('[data-action="retry"]').click()
    expect(page.locator("#itemList .item-card").filter(has_text=failed_id).locator(".badge")).to_have_text("pending")

    public_item = _create_item(
        base_url,
        image_bytes,
        "用户 B 的公开风衣",
        "outerwear",
        user="user_b",
        visibility="public",
    )
    page.locator('#wishForm input[name="sourceItemId"]').fill(public_item["id"])
    with page.expect_response(
        lambda response: response.request.method == "GET"
        and response.url.endswith("/api/v1/wish-items")
    ) as refreshed_wishes:
        with page.expect_response(
            lambda response: response.request.method == "POST"
            and response.url.endswith("/api/v1/wish-items")
        ) as created_wish:
            page.locator('#wishForm button[type="submit"]').click()
    assert created_wish.value.status == 201
    assert refreshed_wishes.value.status == 200
    assert refreshed_wishes.value.json()["data"]["total"] == 1
    wish_card = page.locator("#wishList .item-card").filter(has_text="用户 B 的公开风衣")
    expect(wish_card).to_have_count(1)

    with page.expect_response(re.compile(r"/copy-to-wardrobe$")):
        wish_card.locator('[data-action="copy-wish"]').click()
    expect(page.locator("#itemList")).to_contain_text("用户 B 的公开风衣")

    wish_card = page.locator("#wishList .item-card").filter(has_text="用户 B 的公开风衣")
    with page.expect_response(lambda response: response.request.method == "DELETE"):
        wish_card.locator('[data-action="delete-wish"]').click()
    expect(page.locator("#wishList .item-card")).to_have_count(0)

    page.locator("#userId").fill("user_b")
    with page.expect_response(re.compile(r"/api/v1/items\?")):
        page.locator("#applyIdentity").click()
    expect(page.locator("#token")).to_have_value("dev:user_b")
    expect(page.locator("#itemList")).to_contain_text("用户 B 的公开风衣")
    assert errors == []
