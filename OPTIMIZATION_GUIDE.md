# 🚀 HƯỚNG DẪN TỐI ƯU HÓA TOÀN DIỆN AGENTUI

> Dành riêng cho bạn: Cẩm nang vận hành và khai thác 100% sức mạnh hệ thống **Multi-Agent (1 Claude + 5 Antigravity Pro)** để làm Web, Mobile và AI hiệu quả nhất.

---

## PHẦN 1: TỔNG QUAN CÁC KHU VỰC TRÊN GIAO DIỆN

```
┌─────────────────┬──────────────────────────────────────────────────────────┐
│ VIETHUY /       │ [Tabs 6 Projects]     ▦ Process  🕒 Schedules  ⚡ Skills │
├─────────────────┼──────────────────────────────────────────────────────────┤
│ 📁 Project List │                                                          │
│   • lifedashboard│                    CANVAS ĐỒ THỊ SVG                     │
│   • fitmatch-ai │                 (Kéo thả node, Zoom, Pan)                │
│   • house-renting│                                                          │
│   • app-wallet  │         ┌────────────┐            ┌────────────┐         │
│   • canvas-ai   │         │    BOSS    │───────────▶│ UI_DESIGNER│         │
│   • learning-ai │         └─────┬──────┘            └────────────┘         │
├─────────────────┤               │                                          │
│ 📂 WORKSPACE    │               ▼                   ┌────────────┐         │
│ (Cây thư mục    │         ┌────────────┐            │  FE_LOGIC  │         │
│  xem file &     │         │  BACKEND   │            └────────────┘         │
│  copy path)     │         └────────────┘                                   │
├─────────────────┼──────────────────────────────────────────────────────────┤
│ ⌨️ TASKBAR      │ [Cửa sổ thu nhỏ]                         [Usage Widget 📊]│
└─────────────────┴──────────────────────────────────────────────────────────┘
```

---

## PHẦN 2: WORKSPACE DÙNG LÀM GÌ & CÁCH TỐI ƯU

**Workspace** nằm ở nửa dưới của thanh Sidebar bên trái:

### 1. Công dụng chính:
* **Quản lý tập trung 6 dự án**: Bạn có thể duyệt cây thư mục của cả 6 project cùng lúc mà không cần mở nhiều cửa sổ VS Code hay chuyển qua lại Finder.
* **Biểu tượng kim cương `◆`**: Thư mục nào có dấu kim cương ở đầu chính là thư mục gốc của các dự án đã đăng ký.

### 2. Hai tính năng "đáng tiền" nhất của Workspace:
1. **Xem file nổi (Floating File Viewer)**:
   * Bấm vào bất kỳ file nào (file code `.ts`, `.py`, `.json`, file tài liệu `.md`, file ảnh `.png`, file PDF).
   * Giao diện sẽ mở một cửa sổ nổi riêng biệt hỗ trợ **tô màu cú pháp (Syntax Highlight)**, render Markdown chuẩn chỉnh hoặc xem ảnh/PDF ngay trong app.
2. **Phím tắt Copy đường dẫn siêu tốc (`⌥⌘C`)**:
   * Chọn một file hoặc folder trong cây thư mục $\rightarrow$ Bấm tổ hợp phím **`Option + Command + C`** (hoặc `Alt + Win + C`).
   * Đường dẫn tuyệt đối sẽ được copy ngay vào clipboard để bạn dán vào khung chat giao việc cho Agent (ví dụ: *"Hãy sửa file `/Users/.../src/Navbar.tsx`"*).

---

## PHẦN 3: SCHEDULE DÙNG LÀM GÌ & CÁCH SỬ DỤNG

Nút **`🕒 Schedules`** trên Topbar là **Bộ máy tự động hóa chạy ngầm**:

### 1. Tại sao cần Schedule?
Bình thường khi bạn chat xong 1 câu, Agent trả lời xong là tiến trình CLI sẽ thoát ra để tiết kiệm RAM. Agent không thể tự thức dậy nếu bạn không gửi tin nhắn mới. **Schedule sinh ra để đánh thức Agent chạy định kỳ theo lịch trình.**

### 2. Ba chế độ sử dụng:
* **Chế độ lặp định kỳ (`interval`)**:
  * *Cách dùng:* Gõ lệnh trong khung chat: `/schedule 30m Kiểm tra log lỗi server và ghi vào progress.md`
  * *Kết quả:* Cứ mỗi 30 phút, hệ thống tự động kích hoạt Agent chạy kiểm tra và báo cáo.
* **Chế độ hẹn giờ 1 lần (`once`)**:
  * *Cách dùng:* `/schedule once 2h Chạy kiểm thử lại toàn bộ hệ thống`
  * *Kết quả:* Đúng 2 tiếng sau Agent mới thức dậy chạy 1 lần duy nhất.
* **Chế độ bám đuổi mục tiêu (`until` / Goal Loop)**:
  * *Cách dùng:* Gõ `/track 15m Tìm và sửa hết lỗi TypeScript trong thư mục src`
  * *Kết quả:* Cứ 15 phút Agent tự chạy 1 vòng sửa lỗi. Khi nào sửa hết 100%, Agent tự phát thẻ `<schedule_stop reason="Đã xong"/>` để kết thúc vòng lặp.

### 3. Công tắc Master Switch (Tiết kiệm Token):
Trong menu **`🕒 Schedules`**, có một công tắc Switch Apple ở đầu danh sách. 
* Khi bạn đang tập trung code thủ công và không cần chạy ngầm: **Gạt sang `OFF`** để vô hiệu hóa toàn bộ lịch trình, giúp tiết kiệm triệt để token.

---

## PHẦN 4: SKILL DÙNG LÀM GÌ & CÁCH SỬ DỤNG

Nút **`⚡ Skills`** trên Topbar là **Kho công cụ & Quy trình nghiệp vụ chuẩn hóa**:

### 1. Tại sao cần Skill?
Khi bạn muốn Agent làm một tác vụ chuyên môn cao (như: thiết kế giao diện theo xu hướng mới, bóc tách PDF không bị cắt lẹm, audit lỗ hổng bảo mật...), nếu bạn tự viết prompt thì rất dài và dễ thiếu sót. **Skills là những bộ hướng dẫn chuyên gia đã được đóng gói sẵn.**

### 2. Cách sử dụng:
1. Bấm vào nút **`⚡ Skills`** trên thanh Topbar (bảng kỹ năng sẽ trượt ra từ bên phải).
2. Tìm kỹ năng bạn cần (ví dụ: *modern-web-guidance*, *chrome-extensions*, *generative_ui*...).
3. Bấm nút **`Use`** màu xanh $\rightarrow$ Toàn bộ câu lệnh và ngữ cảnh chuẩn sẽ tự động điền vào khung chat của Agent đang mở $\rightarrow$ Bạn chỉ cần bấm Gửi!

---

## PHẦN 5: QUY TRÌNH VẬN HÀNH CHUẨN 3 BƯỚC (BEST WORKFLOW)

```
BƯỚC 1: Ra đề bài cho BOSS (Claude Opus)
  │  • Mở cửa sổ chat của BOSS.
  │  • Giao mục tiêu: "Hãy tạo trang Quản lý Chi tiêu mới gồm Biểu đồ tròn và Bảng lịch sử".
  │  • BOSS tự phân tích và phát lệnh:
  │      <dispatch agent="UI_DESIGNER">Tạo component Biểu đồ và Bảng với Tailwind</dispatch>
  │      <dispatch agent="FE_LOGIC">Viết Hook useExpenses với React Query và Zustand</dispatch>
  │      <dispatch agent="BACKEND">Viết API endpoint /api/expenses với TypeORM</dispatch>
  ▼
BƯỚC 2: Antigravity Swarm Thực thi Song Song (0 tốn token Claude)
  │  • Cả 3 Worker chạy song song cùng một lúc.
  │  • Ưu tiên dùng Gemini 3.7 Flash High siêu tốc (1M context).
  │  • Tự động chuyển Claude Opus 4.6 Thinking / GPT-OSS và đảo tài khoản nếu hết quota.
  │  • Kết quả tự động gom về sổ cái (Ledger) để BOSS tổng hợp cho bạn.
  ▼
BƯỚC 3: Nghiệm thu bằng AUDIT (Claude Opus)
  │  • Mở cửa sổ chat của AUDIT.
  │  • Gõ: "Hãy kiểm tra lại toàn bộ code vừa viết, rà soát lỗi bảo mật và xác nhận".
  │  • AUDIT sẽ đánh giá chi tiết và phê duyệt hoàn tất.
```

---

## PHẦN 6: BẢNG LỆNH NHANH (SLASH COMMANDS CHEAT SHEET)

Gõ dấu `/` trong bất kỳ ô chat nào để mở menu lệnh:

| Lệnh | Ý nghĩa | Khi nào nên dùng |
| :--- | :--- | :--- |
| `/clear` | Bắt đầu phiên mới | Khi chuyển sang một tính năng mới (giúp agent tập trung hơn). |
| `/compact` | Tự tóm tắt ngữ cảnh | Khi cuộc trò chuyện quá dài, giúp nén gọn bộ nhớ. |
| `/status` | Xem model & trạng thái | Kiểm tra xem agent đang chạy model nào và trạng thái ra sao. |
| `/focus <AGENT_ID>` | Mở nhanh cửa sổ | Nhảy nhanh sang cửa sổ của agent khác trên canvas. |
| `/dispatch <ID> <task>` | Giao việc trực tiếp | Điều phối cưỡng bức một task cho agent con. |
| `/stop` (hoặc phím `Esc`) | Dừng stream tức thì | Hủy ngay lượt chạy đang stream dở để không phí quota. |

---

💡 **Tính năng "Giao việc rồi gập máy" (Detached Run):**
Mọi lượt chạy đều được quản lý độc lập trên server localhost. Khi bạn đã gửi yêu cầu cho BOSS và thấy các worker bắt đầu chạy, bạn có thể **đóng trình duyệt hoặc tắt máy đi ngủ**. Server vẫn âm thầm chạy đến khi hoàn tất và lưu trọn vẹn kết quả vào cơ sở dữ liệu!
