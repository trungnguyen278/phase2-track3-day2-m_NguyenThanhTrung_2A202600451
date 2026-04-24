# Reflection — Lab #17 Multi-Memory Agent

> **Họ tên:** Nguyễn Thành Trung · **MSSV:** 2A202600451 · **VinUni AICB — Phase 2 / Track 3 / Day 02**

## 1. Memory nào giúp agent nhất?

Trong 10 scenario, **profile memory** là loại đóng góp lớn nhất: nó biến các câu "Tên tôi là gì?", "Mình dị ứng cái gì?", "Đề xuất ngôn ngữ" từ chỗ no-mem phải đoán mò thành with-mem trả lời chính xác. **Semantic memory** đứng thứ hai: nó cho phép agent dẫn chiếu tài liệu (LangGraph, Docker Compose networking) mà không cần user nhắc lại. **Episodic memory** hữu ích cho các câu hỏi "lần trước mình gặp vấn đề gì" — đặc biệt khi user không remember chi tiết outcome. **Short-term** gần như luôn cần để duy trì mạch hội thoại, nhưng riêng nó không đủ sau 8 lượt vì sliding window đã drop các lượt cũ.

## 2. Memory nào rủi ro nhất nếu retrieve sai?

**Profile memory là rủi ro nhất** vì:

1. Nó được inject như "sự thật về user" ở đầu prompt → LLM có xu hướng tin tuyệt đối.
2. Một fact sai (vd: allergy sai) có thể dẫn đến tư vấn gây hại thực tế (dị ứng, y tế, tài chính).
3. Nó persistent cross-session, một lần ghi sai → sai mãi nếu không có cơ chế correction.

**Episodic memory rủi ro thứ hai**: nếu agent generalize sai ("user luôn thích X") từ một outcome đơn lẻ, nó có thể tạo bias dai dẳng.

**Semantic memory ít rủi ro hơn** về mặt PII nhưng có rủi ro hallucination: nếu retrieve sai chunk (ví dụ keyword trùng lặp) LLM có thể citeliệu sai một cách rất tự tin.

## 3. PII và privacy

Các rủi ro PII đã nhận diện trong hệ thống hiện tại:

- **Profile store (JSON plaintext)**: đang lưu `name`, `allergy` — allergy thuộc **dữ liệu y tế nhạy cảm** (HIPAA/GDPR special category). File nằm cleartext trên disk local, không mã hoá.
- **Episodic log**: có thể chứa snippet từ conversation (bug report có thể lộ tên dự án, tên khách hàng).
- **Semantic DB (Chroma)**: nếu user paste email/số điện thoại vào FAQ, nó bị embed và lưu vector cleartext.

### Biện pháp cần có (chưa implement đầy đủ):

| Cơ chế | Trạng thái hiện tại | Đề xuất |
|--------|---------------------|---------|
| **Consent** | chưa có | Trước khi ghi profile fact đầu tiên, hỏi user consent rõ ràng. |
| **Deletion / Right to be forgotten** | `ProfileMemory.delete_fact()` và `SemanticMemory.clear()` có sẵn; chưa có UI | Thêm slash command `/forget <key>` và `/wipe` để user trigger. |
| **TTL** | chưa có | Thêm `expires_at` cho profile entry nhạy cảm (allergy: 180 ngày, name: vô hạn). Job dọn dẹp định kỳ. |
| **PII detection** | chưa có | Chạy regex/NER trước khi embed vào semantic (email/phone/CCN → mask hoặc reject). |
| **Encryption at rest** | không | Profile JSON nên mã hoá bằng key do user giữ (AES-GCM). |
| **Audit log** | chỉ có `updated_at` | Log đầy đủ ai/khi nào đọc/ghi profile để phát hiện bất thường. |

### Nếu user yêu cầu "xoá memory":

- **Profile**: xoá từng key hoặc `profile.clear()` (đã có).
- **Episodic**: xoá theo topic/tag (hiện chỉ có `clear()` all — cần thêm selective delete).
- **Semantic**: `_collection.delete(ids=[...])` theo doc id (Chroma hỗ trợ). Nhưng nếu user đóng góp vào knowledge chung → phải tách riêng `user_private` collection vs `public_kb`.
- **Short-term**: tự động expire sau session, không persist.
- **Backups**: nhắc user rằng nếu có snapshot/backup, xoá chỉ có hiệu lực sau khi rotation.

## 4. Limitations kỹ thuật của solution hiện tại

Các limitation ban đầu đã được cải thiện:

| Điểm yếu ban đầu | Cải thiện |
|------------------|-----------|
| Profile chỉ có JSON file | Thêm Redis backend qua `REDIS_URL`, tự phát hiện & fallback JSON khi Redis down (`ProfileMemory.backend`) |
| Episodic search keyword-only | Thêm Chroma vector index (`collection=episodic_kb`) + OpenAI embeddings, fallback keyword khi không có API key |
| Trim priority tĩnh | Adaptive theo `intent` của extractor: `question`/có `query_for_semantic` → SEMANTIC trước; `experience` → EPISODIC trước; `preference`/`fact` → PROFILE trước |

Các limitation còn lại:

1. **Profile conflict "newest wins" không rollback được**: Nếu user nói "À mà khoan, quên lời mình nói" thì agent không khôi phục fact trước đó. Cần version history + soft delete.

2. **Extractor là single LLM call** → latency + cost mỗi turn. Có thể cache theo message hash, hoặc dùng nhiều hơn rule-based cho các pattern thường gặp.

3. **Không có idempotency khi write-back**: nếu mạng lỗi giữa `set_fact` và response, turn có thể bị ghi nhưng không confirm. Cần transaction / pending queue.

4. **Không namespace theo `user_id`**: nhiều user dùng chung file/Redis key sẽ lẫn. Cần prefix `user:{id}:profile:` cho Redis và subdirectory cho JSON.

5. **Embedding model cố định**: khi đổi model → phải re-embed toàn bộ KB. Nên lưu `model_version` trong metadata mỗi doc và detect mismatch khi query.

6. **Adaptive trim chỉ dựa vào intent**: chưa cân nhắc độ liên quan (relevance score) của từng hit. Một profile entry không liên quan có thể đang chiếm slot của semantic hit có liên quan cao.

7. **Scale**: Chroma persistent single-disk OK cho demo. Production cần managed vector DB (Pinecone, Qdrant, pgvector) và Postgres cho episodic audit log. Redis cluster cho profile HA.

## 5. Điều gì sẽ fail khi scale?

- **Episodic log** sẽ tăng tuyến tính theo số turn, search O(n) keyword → chậm sau vài ngàn episodes. Cần index (ElasticSearch / vector + time range filter).
- **Profile conflict giữa nhiều device/session**: nếu user đang login 2 phiên cùng lúc, race condition khi cả hai cùng set_fact. Cần optimistic locking hoặc CRDT.
- **Prompt tokens** sẽ leak nếu KB lớn (10k docs × top-3 hits = ~2k tokens mỗi turn). Cần re-rank / summarize sau retrieval.
- **PII volume**: khi có hàng triệu user × nhiều fact × audit log → compliance cost (GDPR export/delete request phải trả lời trong 30 ngày).

## 6. Key takeaway

> Memory chất lượng = Agent chất lượng, nhưng **memory sai lại nguy hiểm hơn không có memory**, vì LLM tin tuyệt đối vào những gì được inject trong system prompt. Privacy-by-design (consent, TTL, deletion path, audit) không phải tính năng phụ mà là nền tảng. Trong lab này, việc "newest wins" xử lý conflict allergy đã chứng minh rõ: **retrieval quality quyết định outcome**, và cơ chế correction phải rõ ràng ngay từ thiết kế.
