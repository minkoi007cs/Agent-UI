# 📖 AGENTUI SYSTEM HANDBOOK & ARCHITECTURE SPECIFICATION

> **Localhost Multi-Agent Control Plane** bọc các CLI thuê bao (`claude -p`, `antigravity`) — Không tiêu tốn API token đắt đỏ, điều phối song song đa tác tử và trực quan hóa qua đồ thị SVG thời gian thực.

---

## 1. Triết lý & Kiến trúc Cốt lõi (Core Architecture)

Hệ thống được thiết kế theo mô hình **Phân tầng vai trò tối ưu chi phí & hiệu năng (Hierarchical Role & Cost Optimization)**:

```
                               ┌─────────────────────────────┐
                               │   BẠN (USER) GIAO YÊU CẦU   │
                               └──────────────┬──────────────┘
                                              │
                                              ▼
                             ┌──────────────────────────────────┐
                             │    👑 BOSS / ORCHESTRATOR        │
                             │    Model: Claude Opus 4.8        │
                             │    • Lập kế hoạch kiến trúc      │
                             │    • Chia việc & Dispatch        │
                             │    • KHÔNG tự viết code dài      │
                             └──────────────┬───────────────────┘
                                            │ <dispatch agent="...">
                                            ▼
                    ┌────────────────────────────────────────────────────────┐
                    │     👷 CỤM ANTIGRAVITY PRO WORKERS (LÀM VIỆC CHÍNH)    │
                    │         (Tự động xoay vòng 4-5 Tài khoản Pro)          │
                    │                                                        │
                    │  1️⃣ Gemini 3.7 Flash (High) ──▶ Chạy chính, 1M context │
                    │           │ (nếu bận/hết quota)                        │
                    │           ▼                                            │
                    │  2️⃣ Claude Opus 4.6 Thinking──▶ Dự phòng Thinking     │
                    │           │ (nếu bận/hết quota)                        │
                    │           ▼                                            │
                    │  3️⃣ GPT-OSS 120B (Medium)   ──▶ Dự phòng OSS           │
                    │           │ (nếu toàn bộ model trên Acc chạm trần)     │
                    │           ▼                                            │
                    │  🔄 TỰ ĐỘNG ĐẢO SANG TÀI KHOẢN TIẾP THEO (ACC 2, 3, 4) │
                    └───────────────────────┬────────────────────────────────┘
                                            │ Trả kết quả (Ledger)
                                            ▼
                             ┌──────────────────────────────────┐
                             │    🔍 AUDIT & QUALITY ASSURANCE  │
                             │    Model: Claude Opus 4.8        │
                             │    • Rà soát code toàn diện      │
                             │    • Kiểm tra bảo mật & bug      │
                             │    • Nghiệm thu và phê duyệt     │
                             └──────────────────────────────────┘
```

### Điểm đột phá:
1. **Tiết kiệm 95% token Claude**: Claude chỉ chạy ở đầu (BOSS phân tích 1-2 câu rồi dispatch) và cuối (AUDIT nghiệm thu). Toàn bộ hàng chục nghìn dòng code do cụm Antigravity Pro gánh.
2. **Không bao giờ nghẽn Rate-Limit**: Nhờ thuật toán **Tiered Cascade + Account Pool Auto-Rotation**, khi một model hoặc tài khoản hết quota, hệ thống tự nhảy sang model/tài khoản tiếp theo mà không làm gián đoạn lượt chat.
3. **Streaming PTY Line-by-Line**: Kết nối stdout qua `pty.openpty()` với `termios raw mode`, loại bỏ hoàn toàn hiện tượng block-buffer của Node.js, chữ hiển thị tức thì theo thời gian thực.

---

## 2. Danh mục 6 Dự án & Sơ đồ Tác tử Chuyên biệt

Hệ thống đã phân rã chuyên sâu theo đặc thù từng dự án:

### 1. 📊 LifeDashboard (`lifedashboard`)
* **Stack**: Monorepo Turbo (NestJS 11 + React 19 + TypeORM + PostgreSQL).
* **Đồ thị Agent**:
  * 👑 `BOSS` (Claude Opus): Thiết kế kiến trúc monorepo và chia task.
  * 🎨 `UI_DESIGNER` (Antigravity): React 19, Tailwind 4, Lucide icons, Dark/Light Theme, Responsive.
  * ⚡ `FE_LOGIC` (Antigravity): Zustand Store, TanStack Query, Zod Form validation, Routing.
  * 🛠️ `BACKEND` (Antigravity): NestJS 11, TypeORM, PostgreSQL, Google OAuth, JWT, Swagger.
  * 🧪 `QA_TESTER` (Antigravity): Unit test, Mock data, Boundary cases.
  * 🔍 `AUDIT` (Claude Opus): Rà soát bảo mật endpoint và nghiệm thu.

### 2. 👗 FitMatch AI (`fitmatch-ai`)
* **Stack**: Next.js 15 + Supabase + OpenAI Vision AI.
* **Đồ thị Agent**:
  * 👑 `BOSS` (Claude Opus): Quản lý luồng phối đồ và thiết kế prompt AI.
  * 🎨 `UI_DESIGNER` (Antigravity): Giao diện Luxury Lookbook, Animation lướt ảnh.
  * ⚡ `FE_LOGIC` (Antigravity): Supabase Auth, Quiz Flow, API client.
  * 🧠 `AI_ENGINE` (Antigravity): Xử lý bóc tách ảnh quần áo, Prompt sinh đồ.
  * 🔍 `AUDIT` (Claude Opus): Đánh giá thẩm mỹ và bảo mật API key.

### 3. 🏠 House Renting (`house-renting`)
* **Stack**: Nền tảng tìm kiếm và cho thuê nhà trực tuyến.
* **Đồ thị Agent**:
  * 👑 `BOSS` (Claude Opus): Thiết kế schema nhà ở và luồng đặt phòng.
  * 🎨 `UI_DESIGNER` (Antigravity): Giao diện danh sách phòng, Bộ lọc tiện ích, Bản đồ.
  * ⚡ `FE_LOGIC` (Antigravity): Luồng đặt lịch xem nhà, Xác thực người thuê.
  * 🛠️ `BACKEND` (Antigravity): Quản lý căn hộ, Xử lý giao dịch cọc.
  * 🔍 `AUDIT` (Claude Opus): Kiểm định độ an toàn thanh toán.

### 4. 💳 App Wallet (`app-wallet`)
* **Stack**: Expo / React Native Mobile Wallet + Supabase.
* **Đồ thị Agent**:
  * 👑 `BOSS` (Claude Opus): Thiết kế luồng giao dịch tài chính.
  * 📱 `MOBILE_UI` (Antigravity): React Native / Expo UI, Biểu đồ thu chi, Gestures.
  * ⚡ `WALLET_LOGIC` (Antigravity): Số dư ví, QR Pay, Lịch sử giao dịch, Mã hóa.
  * 🔍 `AUDIT` (Claude Opus): Audit tính toàn vẹn số dư và bảo mật OTP.

### 5. 🎓 Canvas AI (`canvas-ai`)
* **Stack**: Chrome Extension Manifest V3 + Python Backend.
* **Đồ thị Agent**:
  * 👑 `BOSS` (Claude Opus): Thiết kế luồng tự động hóa bài tập Canvas LMS.
  * 🧩 `EXTENSION_DEV` (Antigravity): Extension Manifest V3, Content Script, Bắt cookie.
  * 🔄 `BACKEND_SYNC` (Antigravity): Python cào deadline, Đồng bộ bài tập về máy.
  * 🔍 `AUDIT` (Claude Opus): Kiểm tra độ ổn định và bảo mật phiên LMS.

### 6. 🧠 Learning AI (`learning-ai`)
* **Stack**: FastAPI + React Web + AI Flashcard Generator.
* **Đồ thị Agent**:
  * 👑 `BOSS` (Claude Opus): Thuật toán Spaced Repetition.
  * 🎨 `UI_DESIGNER` (Antigravity): Thẻ Flashcard 3D, Chế độ luyện thi.
  * ⚡ `FE_LOGIC` (Antigravity): Tính chuỗi học liên tục (Streak), Lưu kết quả.
  * 🤖 `BACKEND_AI` (Antigravity): FastAPI, Tự động sinh câu hỏi trắc nghiệm từ PDF.
  * 🔍 `AUDIT` (Claude Opus): Đánh giá độ chính xác của câu hỏi AI.

---

## 3. Cấu trúc File & Kỹ thuật Điều phối

```
app/
├── backend/
│   ├── main.py          # FastAPI: SSE Chat, Ledger enrichment, Auto-continuation, Scheduler loop
│   ├── adapters.py      # Claude stream PTY + AntigravityKeyPool + Tiered Model Cascade
│   ├── projects.py      # Quản lý project.yaml, Registry, DAG Edges
│   └── db.py            # SQLite: sessions, messages, overrides, ledger, scheduled_tasks
├── frontend/
│   ├── index.html       # Sidebar, Topbar, Workspace, Floating Windows Container
│   ├── app.js           # SVG DAG Renderer, Window Manager, SSE Client, Slash Commands
│   └── styles.css       # Theme Tokens, Window Chrome, Animations, Apple Switch
├── registry.yaml        # Danh sách 6 projects
└── .antigravity_keys.env # Lưu trữ 4-5 Antigravity Pro Keys an toàn (Gitignored)
```

---

## 4. Hướng dẫn Vận hành Nhanh

```bash
cd app
./run.sh
# Mở trình duyệt tại: http://127.0.0.1:5174
```

* **Khởi đầu phiên làm việc**: Mở cửa sổ chat của **BOSS** $\rightarrow$ Giao mục tiêu lớn.
* **Quan sát trực quan**: Đồ thị SVG sẽ sáng đèn và nhấp nháy đường nối (edge) khi BOSS dispatch cho các Worker.
* **Nghiệm thu**: Mở cửa sổ **AUDIT** để yêu cầu đánh giá sản phẩm sau cùng.
