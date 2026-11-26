"""Record a complete browser walkthrough of the local wardrobe debug console."""

from pathlib import Path
import re
import sys

import httpx
from playwright.sync_api import expect, sync_playwright


BACKEND_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BACKEND_DIR / "data" / "demo-output"
ASSET_DIR = BACKEND_DIR / "demo_assets" / "realistic"
BASE_URL = "http://127.0.0.1:8000"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def api(method: str, path: str, user: str = "user_a", **kwargs):
    with httpx.Client(base_url=BASE_URL, timeout=15, trust_env=False) as client:
        response = client.request(
            method, path, headers={"Authorization": f"Bearer dev:{user}"}, **kwargs
        )
        response.raise_for_status()
        return response.json()["data"]


def main() -> None:
    if not CHROME.is_file():
        raise RuntimeError("未找到 Chrome")
    health = httpx.get(f"{BASE_URL}/health", timeout=10, trust_env=False)
    health.raise_for_status()
    public_item = api("GET", "/api/v1/items?page=1&pageSize=20", user="user_b")["list"][0]
    baseline = api("GET", "/api/v1/items?page=1&pageSize=100")["list"]
    failed_id = next(item["id"] for item in baseline if item["verify_status"] == "failed")
    pending_id = next(item["id"] for item in baseline if item["verify_status"] == "pending")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(CHROME), headless=True, slow_mo=180
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir=str(OUTPUT_DIR),
            record_video_size={"width": 1440, "height": 900},
        )
        page = context.new_page()
        page.set_default_timeout(15000)

        def pause(milliseconds: int = 1800) -> None:
            page.wait_for_timeout(milliseconds)

        def title_card(title: str, subtitle: str, milliseconds: int = 4500) -> None:
            page.evaluate(
                """([title, subtitle]) => {
                    const card = document.createElement('div');
                    card.id = 'demo-title-card';
                    Object.assign(card.style, {
                      position: 'fixed', inset: '0', zIndex: '100000', display: 'grid',
                      placeItems: 'center', padding: '80px', textAlign: 'center',
                      background: 'rgba(37,36,31,.94)', color: 'white',
                      fontFamily: 'Microsoft YaHei, sans-serif'
                    });
                    card.innerHTML = `<div><div style="font-size:42px;font-weight:800;margin-bottom:22px">${title}</div><div style="font-size:23px;line-height:1.8;color:#ddd8cf">${subtitle}</div></div>`;
                    document.body.appendChild(card);
                  }""",
                [title, subtitle],
            )
            pause(milliseconds)
            page.locator('#demo-title-card').evaluate("element => element.remove()")

        def step(text: str, scroll_to=None, milliseconds: int = 3200) -> None:
            if scroll_to is not None:
                scroll_to.scroll_into_view_if_needed()
            page.evaluate(
                """text => {
                    let banner = document.querySelector('#demo-step-banner');
                    if (!banner) {
                      banner = document.createElement('div');
                      banner.id = 'demo-step-banner';
                      Object.assign(banner.style, {
                        position: 'fixed', left: '50%', bottom: '24px', transform: 'translateX(-50%)',
                        zIndex: '99999', width: 'min(900px, calc(100vw - 48px))',
                        padding: '16px 22px', borderRadius: '14px', textAlign: 'center',
                        background: 'rgba(37,36,31,.94)', color: 'white',
                        boxShadow: '0 12px 40px rgba(0,0,0,.28)',
                        font: '700 21px/1.6 Microsoft YaHei, sans-serif'
                      });
                      document.body.appendChild(banner);
                    }
                    banner.textContent = text;
                  }""",
                text,
            )
            if scroll_to is not None:
                scroll_to.evaluate(
                    """element => {
                      document.querySelectorAll('.demo-highlight').forEach(node => {
                        node.classList.remove('demo-highlight'); node.style.outline = '';
                        node.style.outlineOffset = '';
                      });
                      element.classList.add('demo-highlight');
                      element.style.outline = '4px solid rgba(216,95,67,.72)';
                      element.style.outlineOffset = '7px';
                    }"""
                )
            pause(milliseconds)

        page.goto(f"{BASE_URL}/debug/wardrobe?demo=full", wait_until="networkidle")
        expect(page.locator("#itemList .item-card")).to_have_count(10)
        title_card(
            "衣橱功能演示",
            "先看已有衣物和筛选，再演示新增、完整编辑、AI 识别、心愿衣橱与用户切换。",
        )
        step("先点一下“检查服务”。右上角显示绿色，说明网页已经连上后端。", page.locator("#connectionTitle"))
        with page.expect_response(re.compile(r"/health$")):
            page.locator("#healthBtn").click()
        pause(2400)

        items_panel = page.locator("#itemsTitle")
        step("这里是“我的衣橱”。示例数据已经分成 8 类，先刷新一次列表看看。", items_panel)
        page.locator("#loadItemsBtn").click()
        pause(2200)
        step("找衣服时可以按分类筛选。这里选择“上装”，列表只保留上装。", page.locator("#filterForm"))
        with page.expect_response(re.compile(r"category=tops")):
            page.locator('#filterForm select[name="category"]').select_option("tops")
        pause(2600)
        page.locator('#filterForm select[name="category"]').select_option("")
        jeans_card = page.locator("#itemList .item-card").filter(has_text="复古水洗直筒牛仔裤")
        step("衣物卡片里的分类也能直接点击。点“下装”后，同样会自动筛选。", jeans_card)
        with page.expect_response(re.compile(r"category=bottoms")):
            jeans_card.locator('[data-action="filter-category"]').click()
        pause(2600)
        page.locator('#filterForm select[name="category"]').select_option("")
        step("除了分类，还可以按季节、颜色和名称搜索。这里用“秋季、米白、针织”做示范。", page.locator("#filterForm"))
        page.locator('#filterForm select[name="season"]').select_option("autumn")
        pause(1800)
        page.locator('#filterForm select[name="season"]').select_option("")
        page.locator('#filterForm input[name="color"]').fill("米白")
        page.locator('#filterForm input[name="keyword"]').fill("针织")
        page.locator('#filterForm button[type="submit"]').click()
        pause(2800)
        page.locator('#filterForm input[name="color"]').fill("")
        page.locator('#filterForm input[name="keyword"]').fill("")
        page.locator('#filterForm button[type="submit"]').click()

        step("衣物多时可以分页。先把每页改成 5 件，再试试下一页和上一页。", page.locator(".list-toolbar"))
        page.locator('#filterForm select[name="pageSize"]').select_option("5")
        expect(page.locator("#itemList .item-card")).to_have_count(5)
        pause(1800)
        page.locator("#nextPage").click()
        pause(2400)
        page.locator("#prevPage").click()
        pause(2200)
        page.locator('#filterForm select[name="pageSize"]').select_option("20")

        upload_panel = page.locator("#uploadTitle")
        step("下面新增一件衣物。第一步先选择照片并上传，上传后会看到图片预览。", upload_panel)
        page.locator("#imageInput").set_input_files(str(ASSET_DIR / "cream-knit.png"))
        with page.expect_response(re.compile(r"/api/v1/uploads/image$")):
            page.locator("#uploadBtn").click()
        pause(3000)
        step("不使用 AI 也能手动添加。填写名称、分类、颜色、季节和使用场合后保存。", page.locator("#createForm"))
        create_form = page.locator("#createForm")
        create_form.locator('[name="name"]').fill("演示新增针织开衫")
        create_form.locator('[name="category"]').select_option("tops")
        create_form.locator('[name="color"]').fill("奶油白")
        create_form.locator('[name="warmth"]').select_option("3")
        create_form.locator('[name="season"]').select_option(["spring", "autumn"])
        create_form.locator('[name="style"]').select_option(["minimal", "casual"])
        create_form.locator('[name="occasion"]').select_option(["commute", "casual"])
        create_form.locator('[name="visibility"]').select_option("private")
        with page.expect_response(
            lambda response: response.request.method == "POST"
            and response.url.endswith("/api/v1/items")
        ) as created:
            create_form.locator('button[type="submit"]').click()
        created_id = created.value.json()["data"]["id"]
        pause(3000)

        step("新衣物已经出现在列表里。现在点“编辑”，打开完整的衣物信息表单。", items_panel)
        created_card = page.locator("#itemList .item-card").filter(has_text=created_id)
        created_card.locator('[data-action="edit"]').click()
        edit_form = page.locator("#editForm")
        expect(page.locator("#editDialog")).to_be_visible()
        step("这里可以修改全部资料：分类、颜色组、保暖度、材质、图案、季节、风格、场合和公开状态。", page.locator("#editDialog"), 4200)
        edit_form.locator('[name="name"]').fill("演示编辑完成的羊毛外套")
        edit_form.locator('[name="category"]').select_option("outerwear")
        edit_form.locator('[name="color"]').fill("海军蓝")
        edit_form.locator('[name="colors"]').fill("海军蓝, 银灰色")
        edit_form.locator('[name="warmth"]').select_option("5")
        edit_form.locator('[name="material"]').fill("羊毛混纺")
        edit_form.locator('[name="pattern"]').fill("细条纹")
        edit_form.locator('[name="season"]').select_option(["autumn", "winter"])
        edit_form.locator('[name="style"]').select_option(["minimal", "formal"])
        edit_form.locator('[name="occasion"]').select_option(["commute", "formal"])
        edit_form.locator('[name="visibility"]').select_option("public")
        edit_form.locator('[name="isFavorite"]').uncheck()
        pause(4200)
        with page.expect_response(
            lambda response: response.request.method == "PATCH" and created_id in response.url
        ):
            edit_form.locator('button[type="submit"]').click()
        pause(3200)

        step("保存后，刚填写的完整资料会显示在卡片上。还可以把衣物标成常用。", items_panel)
        created_card = page.locator("#itemList .item-card").filter(has_text=created_id)
        created_card.locator('[data-action="favorite"]').click()
        pause(2400)
        step("再次点击就能取消常用，状态切换会立即写入数据库。", created_card)
        page.locator("#itemList .item-card").filter(has_text=created_id).locator('[data-action="favorite"]').click()
        pause(2400)

        step("接着演示 AI 识别。仍然先上传照片，再点击“AI 识别”。", upload_panel)
        page.locator("#imageInput").set_input_files(str(ASSET_DIR / "denim-overshirt.png"))
        with page.expect_response(re.compile(r"/api/v1/uploads/image$")):
            page.locator("#uploadBtn").click()
        pause(2600)
        page.once("dialog", lambda dialog: dialog.accept())
        with page.expect_response(re.compile(r"/api/v1/ai/recognize$")) as recognized:
            page.locator("#recognizeBtn").click()
        recognized_id = recognized.value.json()["data"]["id"]
        pause(2800)
        step("识别结果不会直接当成最终数据，而是先进入“待确认”状态。确认无误后再保存。", items_panel)
        page.locator("#itemList .item-card").filter(has_text=recognized_id).locator('[data-action="confirm"]').click()
        pause(2600)

        step("如果 AI 暂时失败，照片和记录都不会丢。点击“重试识别”即可重新处理。", items_panel)
        failed_card = page.locator("#itemList .item-card").filter(has_text=failed_id)
        failed_card.locator('[data-action="retry"]').click()
        pause(2600)
        step("重试成功后会回到“待确认”，检查后再点“确认”即可。", failed_card)
        page.locator("#itemList .item-card").filter(has_text=failed_id).locator('[data-action="confirm"]').click()
        pause(2400)
        page.locator("#itemList .item-card").filter(has_text=pending_id).locator('[data-action="confirm"]').click()

        wish_panel = page.locator("#wishTitle")
        step("心愿衣橱用来收藏其他用户公开的衣物。先刷新，再把这件风衣复制到自己的衣橱。", wish_panel, 3800)
        page.locator("#loadWishesBtn").click()
        wish_card = page.locator("#wishList .item-card").first
        wish_card.locator('[data-action="copy-wish"]').click()
        pause(2800)
        step("不想继续收藏时可以取消；知道公开衣物的 ID，也可以重新收藏。", wish_panel)
        page.locator("#wishList .item-card").first.locator('[data-action="delete-wish"]').click()
        pause(2400)
        page.locator('#wishForm input[name="sourceItemId"]').fill(public_item["id"])
        page.locator('#wishForm button[type="submit"]').click()
        pause(2800)

        connection = page.locator("#connectionTitle")
        step("为了验证数据隔离，现在切换到 user_b。切换后只能管理这个用户自己的衣物。", connection, 3800)
        page.locator("#userId").fill("user_b")
        page.locator("#applyIdentity").click()
        expect(page.locator("#token")).to_have_value("dev:user_b")
        expect(page.locator("#itemList")).to_contain_text("卡其色经典风衣")
        pause(3000)
        step("再切回 user_a，刚才的衣橱数据会重新显示。", connection)
        page.locator("#userId").fill("user_a")
        page.locator("#applyIdentity").click()
        pause(2600)

        step("最后删除本次演示新增的衣物。这里采用软删除，列表不再显示，但历史记录仍可保留。", items_panel, 3800)
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator("#itemList .item-card").filter(has_text=created_id).locator('[data-action="delete"]').click()
        expect(page.locator("#itemList")).not_to_contain_text(created_id)
        pause(2800)

        console = page.locator("#consoleTitle")
        step("右侧是请求记录。联调时可以在这里查看操作是否成功，确认后也可以清空。", console, 3800)
        page.locator("#clearLog").click()
        pause(2400)
        title_card(
            "演示结束",
            "衣物筛选、分页、上传、新增、完整编辑、常用状态、AI 识别、失败重试、心愿衣橱、身份切换和删除都已演示。",
            6000,
        )

        video = page.video
        page.close()
        context.close()
        browser.close()
        source = Path(video.path())
        target = OUTPUT_DIR / "wardrobe-full-demo.webm"
        source.replace(target)
        print(target)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"recording failed: {exc}", file=sys.stderr)
        raise
