------------------------------
## Lab #17: Build Multi-Memory Agent với LangGraph
Giảng viên: VinUni AICB
Thời gian: 2 giờ
Nội dung: Ngày 17 | Tuần 4
------------------------------
## 🎯 Mục tiêu bài học
Xây dựng một Multi-Memory Agent có khả năng quản lý thông tin linh hoạt qua nhiều tầng bộ nhớ.

* Deliverable: Agent hoàn chỉnh với full memory stack.
* Benchmark Report: So sánh hiệu năng giữa Agent có bộ nhớ và không có bộ nhớ trên 10 hội thoại đa lượt (multi-turn).

------------------------------
## 🧪 Demo & Thực hành: Khả năng ghi nhớ qua 3 Sessions
Kịch bản thử nghiệm khả năng lưu trữ User Preferences:

   1. Session 1: User nói "Tôi thích Python, không thích Java" → Agent tự động trích xuất và ghi vào Redis.
   2. Session 2 (New Process): Agent load memory từ Redis → Chủ động đề xuất giải pháp bằng Python mà không cần hỏi lại.
   3. Session 3: Agent truy vấn Episodic Memory (hồi ức) → Nhớ lại "User từng bị bối rối về async/await" → Tự động bổ sung giải pháp giải thích chi tiết hơn.
   4. So sánh: Đánh giá Agent có Memory vs. Không Memory dựa trên:
   * Response Relevance: Độ liên quan của câu trả lời.
      * User Satisfaction: Mức độ hài lòng của người dùng.
   
------------------------------
## 🛠️ Các bước thực hành chi tiết## 1. Triển khai 4 Memory Backends

* Short-term: ConversationBufferMemory (Lưu ngữ cảnh tức thời).
* Long-term: Redis (Lưu sở thích, profile người dùng lâu dài).
* Episodic: JSON Log (Lưu lại các trải nghiệm/sự kiện cụ thể trong quá khứ).
* Semantic: ChromaDB (Tìm kiếm kiến thức dựa trên ý nghĩa ngữ nghĩa).

## 2. Xây dựng Memory Router
Thiết kế logic để Agent chọn loại bộ nhớ phù hợp dựa trên Query Intent:

* User Preference (Sở thích) vs. Factual Recall (Sự thật) vs. Experience Recall (Kinh nghiệm).

## 3. Quản lý Context Window

* Auto-trim: Tự động cắt tỉa khi hội thoại gần đạt giới hạn Token.
* Priority-based Eviction: Xóa bộ nhớ dựa trên phân cấp 4 tầng ưu tiên.

## 4. Benchmark & Báo cáo
So sánh trên 10 cuộc hội thoại multi-turn để đo lường:

* Response Relevance: Tỉ lệ phản hồi đúng trọng tâm.
* Context Utilization: Hiệu quả sử dụng ngữ cảnh.
* Token Efficiency: Tối ưu hóa lượng token tiêu thụ.
* Output: GitHub repo + Bảng phân tích Memory Hit Rate và Token Budget Breakdown.

------------------------------
## 💡 Tổng kết — Key Takeaways

   1. No "One size fits all": Hệ thống Production cần ít nhất Short-term + Long-term; bổ sung Episodic/Semantic tùy theo bài toán cụ thể.
   2. Retrieval Quality = Agent Quality: Truy xuất bộ nhớ kém dẫn đến ngữ cảnh sai, gây ra câu trả lời sai (Hallucination).
   3. Memory Write-back Design: Cần thiết kế kỹ lưỡng: Nhớ cái gì? Khi nào ghi? Xử lý xung đột thông tin như thế nào? TTL (thời gian sống) bao lâu?
   4. Privacy by Design: Quyền riêng tư (GDPR) không phải là phần bổ sung sau cùng, mà phải được tích hợp ngay từ khâu thiết kế kiến trúc bộ nhớ.

