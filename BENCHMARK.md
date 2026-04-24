# Benchmark: No-memory vs With-memory

> **Họ tên:** Nguyễn Thành Trung · **MSSV:** 2A202600451 · **Lab #17 — VinUni AICB**

**Model:** gpt-4o-mini | **Scenarios:** 10 multi-turn conversations

## Kết quả tổng quan

| # | Category | Scenario | No-mem | With-mem | Δ prompt tokens |
|---|----------|----------|:------:|:--------:|----------------:|
| 1 | profile | Profile recall: tên user sau 4 lượt | ❌ | ✅ | +392 |
| 2 | profile | Profile recall: ngôn ngữ yêu thích | ✅ | ✅ | +314 |
| 3 | profile | Profile recall: nghề nghiệp | ❌ | ✅ | +330 |
| 4 | conflict | Conflict update: dị ứng sữa bò → đậu nành | ❌ | ✅ | +570 |
| 5 | episodic | Episodic recall: bug Docker/Postgres | ❌ | ✅ | +125 |
| 6 | episodic | Episodic recall: nhầm async/await | ✅ | ✅ | +129 |
| 7 | semantic | Semantic retrieval: LangGraph là gì | ❌ | ✅ | +98 |
| 8 | semantic | Semantic retrieval: Docker Compose networking | ❌ | ✅ | +92 |
| 9 | trim | Trim/token budget: 12 lượt chit-chat rồi recall | ❌ | ✅ | +803 |
| 10 | combine | Combine profile + semantic | ❌ | ✅ | +212 |

- No-memory pass rate: **2/10**
- With-memory pass rate: **10/10**
- Tổng prompt tokens: no-mem **675**, with-mem **3740** (+3065 cho memory injection)

## Chi tiết từng scenario

### 1. Profile recall: tên user sau 4 lượt  _[profile]_
- **Probe:** Tên tôi là gì?
- **No-memory** (FAIL, tokens={'prompt': 62, 'completion': 19}): _Xin lỗi, tôi không biết tên của bạn. Bạn có thể cho tôi biết được không?_
- **With-memory** (PASS, tokens={'prompt': 454, 'completion': 6}): _Tên bạn là Linh._

### 2. Profile recall: ngôn ngữ yêu thích  _[profile]_
- **Probe:** Bạn đề xuất ngôn ngữ nào cho mình viết script tự động hoá?
- **No-memory** (PASS, tokens={'prompt': 74, 'completion': 57}): _Nếu bạn muốn viết script tự động hóa, Python là một lựa chọn tuyệt vời nhờ vào cú pháp dễ hiểu và nhiều thư viện hỗ trợ. Ngoài ra, bạn cũng…_
- **With-memory** (PASS, tokens={'prompt': 388, 'completion': 56}): _Mình đề xuất bạn tiếp tục sử dụng Python để viết script tự động hóa. Python có nhiều thư viện mạnh mẽ cho tự động hóa như `selenium`, `requ…_

### 3. Profile recall: nghề nghiệp  _[profile]_
- **Probe:** Tóm tắt giúp mình biết mình làm nghề gì.
- **No-memory** (FAIL, tokens={'prompt': 69, 'completion': 28}): _Xin lỗi, mình không có thông tin về nghề nghiệp của bạn. Bạn có thể cho mình biết thêm về công việc của bạn không?_
- **With-memory** (PASS, tokens={'prompt': 399, 'completion': 28}): _Bạn là một data scientist tại VinUni, chuyên làm việc với dữ liệu để phân tích và phát triển các mô hình dự đoán._

### 4. Conflict update: dị ứng sữa bò → đậu nành  _[conflict]_
- **Probe:** Mình dị ứng cái gì?
- **No-memory** (FAIL, tokens={'prompt': 64, 'completion': 28}): _Mình không có thông tin về dị ứng của bạn. Bạn có thể chia sẻ thêm chi tiết để mình giúp bạn tốt hơn không?_
- **With-memory** (PASS, tokens={'prompt': 634, 'completion': 25}): _Bạn dị ứng đậu nành. Hãy cẩn thận với các sản phẩm chứa đậu nành nhé!_

### 5. Episodic recall: bug Docker/Postgres  _[episodic]_
- **Probe:** Lần trước mình debug docker với postgres, giải pháp là gì?
- **No-memory** (FAIL, tokens={'prompt': 71, 'completion': 217}): _Để debug Docker với PostgreSQL, bạn có thể thử các bước sau:  1. **Kiểm tra Logs**: Sử dụng lệnh `docker logs <container_id>` để xem log củ…_
- **With-memory** (PASS, tokens={'prompt': 196, 'completion': 29}): _Giải pháp là thay đổi từ localhost sang sử dụng service name 'db' trong docker-compose để container backend có thể kết nối với postgres._

### 6. Episodic recall: nhầm async/await  _[episodic]_
- **Probe:** Mình hay quên gì khi viết async Python?
- **No-memory** (PASS, tokens={'prompt': 68, 'completion': 183}): _Khi viết async trong Python, bạn có thể hay quên những điều sau:  1. **Sử dụng `await`**: Đảm bảo bạn sử dụng `await` khi gọi các hàm async…_
- **With-memory** (PASS, tokens={'prompt': 197, 'completion': 57}): _Khi viết async Python, bạn thường quên rằng phải sử dụng `await` cho mọi coroutine để tránh chặn thread. Nếu không, IO sẽ block và gây ra v…_

### 7. Semantic retrieval: LangGraph là gì  _[semantic]_
- **Probe:** LangGraph quản lý state kiểu gì?
- **No-memory** (FAIL, tokens={'prompt': 65, 'completion': 68}): _LangGraph quản lý state thông qua việc sử dụng các cấu trúc dữ liệu như cây hoặc đồ thị để theo dõi và cập nhật trạng thái của các thành ph…_
- **With-memory** (PASS, tokens={'prompt': 163, 'completion': 37}): _LangGraph sử dụng StateGraph để quản lý state thông qua TypedDict. Mỗi node trong StateGraph nhận một state và trả về một dict để hợp nhất …_

### 8. Semantic retrieval: Docker Compose networking  _[semantic]_
- **Probe:** Hai container docker nối với nhau thế nào?
- **No-memory** (FAIL, tokens={'prompt': 66, 'completion': 179}): _Để nối hai container Docker với nhau, bạn có thể sử dụng Docker networks. Dưới đây là các bước cơ bản:  1. **Tạo một network**:    ```bash …_
- **With-memory** (PASS, tokens={'prompt': 158, 'completion': 22}): _Hai container Docker có thể kết nối với nhau bằng cách sử dụng service name trong Docker Compose thay vì localhost._

### 9. Trim/token budget: 12 lượt chit-chat rồi recall  _[trim]_
- **Probe:** Tên mình là gì?
- **No-memory** (FAIL, tokens={'prompt': 62, 'completion': 19}): _Xin lỗi, mình không biết tên của bạn. Bạn có thể cho mình biết được không?_
- **With-memory** (PASS, tokens={'prompt': 865, 'completion': 6}): _Tên bạn là Khánh!_

### 10. Combine profile + semantic  _[combine]_
- **Probe:** Giới thiệu ngắn về Redis cho mình (nhớ gọi tên mình nhé).
- **No-memory** (FAIL, tokens={'prompt': 74, 'completion': 94}): _Chào bạn! Redis là một hệ thống lưu trữ dữ liệu dạng key-value, nổi bật với tốc độ nhanh và khả năng xử lý dữ liệu trong bộ nhớ. Nó thường …_
- **With-memory** (PASS, tokens={'prompt': 286, 'completion': 68}): _Redis là một in-memory key-value store, Minh ạ, nổi bật với tốc độ truy xuất dưới 1ms. Nó rất phù hợp cho các ứng dụng cần hiệu suất cao và…_
