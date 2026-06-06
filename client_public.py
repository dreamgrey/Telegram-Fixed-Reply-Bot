"""
Telegram Fixed-Reply Bot
========================
A Telegram bot that automatically replies to user messages with a preset
multi-stage conversation flow. Includes human-like typing delays, concurrency
safety, persistent state, and daily statistics logging.

Customization Guide:
  - MSG_1, MSG_2, MSG_2_5, MSG_3: Your conversation script
  - DOWNLOAD_LINK: Your promotion/target link
  - STAGE_2_TIMEOUT: Wait time before auto-sending MSG_3
  - .env file: Your Telegram API credentials and proxy settings
"""

import os
import json
import time
import random
import asyncio
import signal
import sys
from pathlib import Path
from telethon import TelegramClient, events

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[OK] Loaded config from: {env_path}")
except ImportError:
    pass

# ============================================
# Telegram API 凭证
# ============================================
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")

if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
    raise ValueError(
        "[ERROR] Telegram API credentials not found\n"
        "Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env"
    )

# ============================================
# 【自定义】消息内容 - 请替换为你自己的话术
# ============================================
# 提示: 这是一个 3 句流程
#   Stage 0: 用户第一次发消息 → 发送 MSG_1 + MSG_2 + MSG_2_5（连续发送）
#   Stage 1: 用户回复或5分钟超时 → 发送 MSG_3
#   Stage 2: 不再回复该用户

DOWNLOAD_LINK = os.getenv("DOWNLOAD_LINK", "https://example.com/your-link")

# --- 第1条消息：引导文案 ---
MSG_1 = (
    "Hi! Thanks for reaching out. "
    "Please check out the link below for something special."
)

# --- 第2条消息：链接 ---
MSG_2 = DOWNLOAD_LINK

# --- 第2.5条消息：简短催促 ---
MSG_2_5 = "Check it out 😉"

# --- 第3条消息：跟进/催促 ---
MSG_3 = (
    "Did you check the link? "
    "Make sure to follow through, it's worth your time!"
)

# --- 超时时间：等待用户回复多久后自动发送 MSG_3（单位：秒）---
STAGE_2_TIMEOUT = 300  # 5 minutes

# --- 是否处理启动前的离线消息 ---
PROCESS_OFFLINE = os.getenv("PROCESS_OFFLINE", "false").lower() in ("true", "1", "yes", "on")

# ============================================
# 持久化文件
# ============================================
COMPLETED_USERS_FILE = Path(__file__).parent.parent / 'completed_users.json'
_completed_users = set()

# 每日统计日志（以日期为维度）
DAILY_STATS_FILE = Path(__file__).parent.parent / 'daily_stats.json'
_daily_stats = {}
_today = time.strftime('%Y-%m-%d')


def _get_today_key():
    return time.strftime('%Y-%m-%d')


def load_daily_stats():
    """启动时加载每日统计数据"""
    global _daily_stats
    if DAILY_STATS_FILE.exists():
        try:
            with open(DAILY_STATS_FILE, 'r', encoding='utf-8') as f:
                _daily_stats = json.load(f)
            today = _get_today_key()
            today_data = _daily_stats.get(today, {})
            print(f"[OK] Loaded daily stats ({len(_daily_stats)} days) | "
                  f"Today: replied={today_data.get('replied',0)}, "
                  f"completed={today_data.get('completed',0)}")
        except Exception as e:
            print(f"[WARN] Failed to load daily stats: {e}")
            _daily_stats = {}
    else:
        _daily_stats = {}


def save_daily_stats():
    """保存每日统计数据到磁盘"""
    try:
        with open(DAILY_STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(_daily_stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARN] Failed to save daily stats: {e}")


def _ensure_today():
    """确保当天记录存在"""
    today = _get_today_key()
    if today not in _daily_stats:
        _daily_stats[today] = {"replied": 0, "completed": 0}
    return today


def record_reply(user_id):
    """记录一次回复（去重：同一用户每天只计1次回复）"""
    today = _ensure_today()
    key = f"_{today}_replied_uids"
    uid_set = getattr(record_reply, key, None)
    if uid_set is None:
        uid_set = set()
        setattr(record_reply, key, uid_set)
    if user_id not in uid_set:
        uid_set.add(user_id)
        _daily_stats[today]["replied"] += 1


def record_completion(user_id):
    """记录一次完成（去重：同一用户每天只计1次完成）"""
    today = _ensure_today()
    key = f"_{today}_completed_uids"
    uid_set = getattr(record_completion, key, None)
    if uid_set is None:
        uid_set = set()
        setattr(record_completion, key, uid_set)
    if user_id not in uid_set:
        uid_set.add(user_id)
        _daily_stats[today]["completed"] += 1
    save_daily_stats()


def get_today_stats():
    """获取今日统计"""
    today = _get_today_key()
    return _daily_stats.get(today, {"replied": 0, "completed": 0})


def get_stats_summary(days=7):
    """获取最近N天的统计摘要"""
    all_days = sorted(_daily_stats.keys(), reverse=True)[:days]
    total_replied = sum(_daily_stats.get(d, {}).get("replied", 0) for d in all_days)
    total_completed = sum(_daily_stats.get(d, {}).get("completed", 0) for d in all_days)
    return {
        "days": len(all_days),
        "total_replied": total_replied,
        "total_completed": total_completed,
        "detail": {d: _daily_stats[d] for d in all_days}
    }


def load_completed_users():
    """启动时加载已完成的用户ID"""
    global _completed_users
    if COMPLETED_USERS_FILE.exists():
        try:
            with open(COMPLETED_USERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            _completed_users = set(data.get('users', []))
            print(f"[OK] Loaded {len(_completed_users)} completed user(s) from disk")
        except Exception as e:
            print(f"[WARN] Failed to load completed users: {e}")
            _completed_users = set()
    else:
        _completed_users = set()


def save_completed_users():
    """保存已完成的用户ID到磁盘"""
    try:
        with open(COMPLETED_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'users': list(_completed_users),
                'updated': time.strftime('%Y-%m-%d %H:%M:%S')
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARN] Failed to save completed users: {e}")


def mark_user_completed(user_id):
    """标记用户为已完成并立即保存"""
    _completed_users.add(user_id)
    save_completed_users()


async def auto_save_loop():
    """后台定期保存（防止异常退出丢失数据）"""
    while True:
        await asyncio.sleep(60)
        save_completed_users()
        save_daily_stats()


# ============================================
# Telethon 客户端初始化（支持代理）
# ============================================
PROXY_URL = os.getenv("TELEGRAM_PROXY")

if PROXY_URL:
    import re as _re
    m = _re.match(r'(socks[45]|http)://([^:]+):(\d+)', PROXY_URL)
    if m:
        ptype, phost, pport = m.group(1), m.group(2), int(m.group(3))
        print(f"[OK] Using proxy: {ptype}://{phost}:{pport}")
        client = TelegramClient('fixed_session', TELEGRAM_API_ID, TELEGRAM_API_HASH,
                               proxy=(ptype, phost, pport))
    else:
        print("[WARN] Invalid TELEGRAM_PROXY format, running without proxy")
        client = TelegramClient('fixed_session', TELEGRAM_API_ID, TELEGRAM_API_HASH)
else:
    client = TelegramClient('fixed_session', TELEGRAM_API_ID, TELEGRAM_API_HASH)

# ============================================
# 用户状态管理
# ============================================
_user_states = {}
_user_locks = {}


def get_state(uid):
    if uid not in _user_states:
        initial_stage = 2 if uid in _completed_users else 0
        _user_states[uid] = {"stage": initial_stage, "timer": None, "lock": asyncio.Lock()}
    return _user_states[uid]


def get_lock(uid):
    if uid not in _user_locks:
        _user_locks[uid] = asyncio.Lock()
    return _user_locks[uid]


def cancel_timer(uid):
    state = get_state(uid)
    if state["timer"] and not state["timer"].done():
        state["timer"].cancel()
    state["timer"] = None


async def send_stage_3_later(user_id, event):
    """超时后自动发送第3条消息"""
    try:
        await asyncio.sleep(STAGE_2_TIMEOUT)
        state = get_state(user_id)
        if state["stage"] == 1:
            state["stage"] = 2
            mark_user_completed(user_id)
            record_completion(user_id)
            try:
                await event.respond(MSG_3)
                print(f"📤 [Auto] Stage2 (timeout): {MSG_3[:50]}...")
            except Exception as e:
                print(f"❌ Auto-send failed: {e}")
    except asyncio.CancelledError:
        pass


async def handle_message_event(event):
    """
    消息处理核心逻辑
    带延迟（模拟人工）、并发锁（防止错乱）、状态机（3阶段流程）
    """
    user_id = event.sender_id

    if event.text:
        print(f"📩 Received from {user_id}: '{event.text[:50]}'")
    else:
        print(f"📩 Received from {user_id}: [non-text: {getattr(event.message, 'media', None)}]")

    lock = get_lock(user_id)

    async with lock:
        state = get_state(user_id)

        if state["stage"] >= 2:
            return

        # Step 1: 等待 5-10 秒后标记已读
        read_delay = random.uniform(5, 10)
        print(f"⏳ User {user_id}: waiting {read_delay:.1f}s before mark_read...")
        await asyncio.sleep(read_delay)

        try:
            await event.mark_read()
        except Exception:
            pass

        # Step 2: 等待 10-20 秒后开始回复（模拟人类打字）
        typing_delay = random.uniform(10, 20)
        print(f"⏳ User {user_id}: waiting {typing_delay:.1f}s before reply...")
        await asyncio.sleep(typing_delay)

        if state["stage"] == 0:
            # ---- Stage 0: 首次回复 ----
            state["stage"] = 1

            # 记录今日回复统计（去重）
            record_reply(user_id)

            # 发送 MSG_1
            try:
                await event.respond(MSG_1)
                print(f"📤 Stage0 Msg1: {MSG_1}")
            except Exception as e:
                print(f"❌ Send failed: {e}")
                return

            # 发送 MSG_2（链接）
            try:
                await event.respond(MSG_2)
                print(f"📤 Stage0 Msg2: {MSG_2}")
            except Exception as e:
                print(f"❌ Send failed: {e}")
                return

            # 发送 MSG_2_5
            try:
                await event.respond(MSG_2_5)
                print(f"📤 Stage0 Msg2.5: {MSG_2_5}")
            except Exception as e:
                print(f"❌ Send failed: {e}")

            # 启动超时定时器（5分钟后自动发 MSG_3）
            state["timer"] = asyncio.create_task(
                send_stage_3_later(user_id, event)
            )

        elif state["stage"] == 1:
            # ---- Stage 1: 用户回复了 ----
            cancel_timer(user_id)

            state["stage"] = 2
            mark_user_completed(user_id)
            record_completion(user_id)

            delay = random.uniform(1, 3)
            await asyncio.sleep(delay)

            # 发送 MSG_3
            try:
                await event.respond(MSG_3)
                print(f"📤 Stage1 Msg3 (reply): {MSG_3[:50]}...")
            except Exception as e:
                print(f"❌ Send failed: {e}")


async def process_offline_messages():
    """启动时处理离线积压消息"""
    print("📥 Checking offline messages...")

    try:
        from collections import defaultdict
        user_latest = defaultdict(list)

        async for dialog in client.iter_dialogs():
            if not dialog.is_user or dialog.unread_count == 0:
                continue
            try:
                msgs = await client.get_messages(
                    dialog.entity,
                    limit=min(dialog.unread_count, 20),
                    unread=True,
                    incoming=True
                )
                for msg in msgs:
                    if msg.sender_id:
                        user_latest[msg.sender_id].append(msg)
            except Exception:
                continue

        if not user_latest:
            print("   No offline messages")
            return

        count = 0
        for uid, msgs in user_latest.items():
            latest = msgs[0]
            text_preview = latest.text[:50] if latest.text else "[non-text]"
            print(f"   📩 Offline from {uid}: '{text_preview}...'")

            try:
                await latest.mark_read()
            except Exception:
                pass

            state = get_state(uid)
            if state["stage"] >= 2:
                continue

            class FakeEvent:
                async def respond(self, text):
                    return await latest.respond(text)

            fake_event = FakeEvent()

            try:
                await fake_event.respond(MSG_1)
                await fake_event.respond(MSG_2)
                await fake_event.respond(MSG_2_5)
                print(f"   ✅ Offline 1+2+2.5 sent to {uid}")

                state["stage"] = 1
                state["timer"] = asyncio.create_task(
                    send_stage_3_later(uid, fake_event)
                )
                count += 1
                await asyncio.sleep(2)
            except Exception as e:
                print(f"   ❌ Offline reply failed: {e}")

        print(f"   📊 Processed {count} offline conversation(s)")

    except Exception as e:
        print(f"   ⚠️ Error processing offline messages: {e}")


async def main():
    await client.start()

    # 加载持久化数据
    load_completed_users()
    load_daily_stats()

    print("\n" + "=" * 50)
    print("  🤖 Telegram Fixed-Reply Bot")
    print("=" * 50)
    print(f"  🔗 Link: {DOWNLOAD_LINK}")
    print(f"  ⏱️  Stage2 timeout: {STAGE_2_TIMEOUT}s")
    print(f"  📬 Offline: {'ON' if PROCESS_OFFLINE else 'OFF'}")
    print(f"  📝 Flow: Msg1+Msg2+Msg2.5 -> wait/reply -> Msg3 -> DONE")
    print(f"  ⏱️  Typing delay: 15-30s total")
    print(f"  ✅ Completed users: {len(_completed_users)} (persisted)")
    today_s = get_today_stats()
    summary = get_stats_summary(7)
    print(f"  📊 Today: replied={today_s['replied']}, completed={today_s['completed']}")
    print(f"  📈 7d total: replied={summary['total_replied']}, completed={summary['total_completed']}")

    if PROCESS_OFFLINE:
        await process_offline_messages()
    else:
        print("   (offline skipped)")

    # 启动后台自动保存任务
    save_task = asyncio.create_task(auto_save_loop())

    print("\n🔍 Online and listening...\n")

    client.add_event_handler(handle_message_event, events.NewMessage(incoming=True))

    # 断线自动重连
    MAX_RETRIES = 10
    RETRY_DELAY_BASE = 5
    try:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                await client.run_until_disconnected()
                print("[INFO] Normal disconnect (user initiated?)")
                break
            except ConnectionError as e:
                print(f"\n⚠️ Connection lost: {e}")
                if attempt < MAX_RETRIES:
                    delay = min(RETRY_DELAY_BASE * attempt, 60)
                    print(f"🔄 Reconnecting in {delay}s... ({attempt}/{MAX_RETRIES})")
                    await asyncio.sleep(delay)
                    try:
                        await client.connect()
                        print("✅ Reconnected successfully")
                    except Exception as conn_err:
                        print(f"❌ Reconnect failed: {conn_err}")
                else:
                    print(f"❌ Max retries ({MAX_RETRIES}) reached, giving up")
            except (KeyboardInterrupt, SystemExit):
                raise
    finally:
        save_task.cancel()
        save_completed_users()
        save_daily_stats()
        print("[OK] All data saved to disk")


if __name__ == '__main__':
    def handle_exit(signum, frame):
        print("\n🛑 Shutting down gracefully...")
        save_completed_users()
        save_daily_stats()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)
    client.loop.run_until_complete(main())