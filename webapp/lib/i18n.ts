/**
 * Vietnamese translations for AI Documentary Factory
 * UI: Tiếng Việt | Video Content: English (US/UK)
 */

export const vi = {
  // === Header & General ===
  appName: "AI Documentary Factory",
  tagline: "Tạo phim tài liệu từ chủ đề bất kỳ",

  // === Home Page ===
  homeTitle: "Biến một chủ đề thành phim tài liệu.",
  homeDescription:
    "Nhập một câu hỏi hoặc chủ đề. Hệ thống sẽ nghiên cứu, viết kịch bản, tạo lời bình, hoạt hình hóa và render video 2 phút — sau đó tự động cắt thành Short 9:16.",

  // === Form ===
  formLabel: "Phim tài liệu nói về điều gì?",
  formPlaceholder: "VD: How Did Ancient Humans Survive Deadly Winters?",
  buttonGenerate: "Tạo phim tài liệu",
  buttonStarting: "Đang khởi động...",
  exampleLabel: "Hoặc thử một ví dụ:",

  // === Jobs List ===
  jobsTitle: "Danh sách công việc",
  jobsLink: "Xem tất cả công việc →",
  loading: "Đang tải...",
  noJobs: "Chưa có công việc nào. Bắt đầu từ trang chủ.",
  jobCreated: "Đã tạo",

  // === Job Detail ===
  backToHome: "← Video mới",
  pipeline: "Quy trình",
  viewStoryboard: "Xem Storyboard →",
  viewCharacters: "Xem nhân vật →",
  viewAssets: "Xem tài nguyên →",
  finalRender: "🎬 Render cuối cùng →",
  result: "Kết quả",
  documentaryLabel: "Phim tài liệu (16:9)",
  shortLabel: "Short (9:16)",
  stagesNotStarted: "Các giai đoạn chưa bắt đầu...",

  // === Error Messages ===
  errorStartJob: "Không thể bắt đầu công việc",
  errorLoadJob: "Không thể tải công việc",
  jobFailed: "Công việc thất bại",

  // === Stage Names (Pipeline) ===
  stages: {
    research: "Nghiên cứu",
    thesis: "Luận điểm",
    titles: "Tiêu đề",
    script: "Kịch bản",
    storyboard: "Storyboard",
    assets: "Tài nguyên",
    narration: "Lời bình",
    scene_json: "Scene JSON",
    validate: "Xác thực",
    render: "Render",
    shorts: "Shorts",
  },

  // === Status ===
  status: {
    pending: "Đang chờ",
    running: "Đang chạy",
    completed: "Hoàn thành",
    failed: "Thất bại",
    skipped: "Bỏ qua",
  },

  // === Render Page ===
  render: {
    title: "RENDER CUỐI CÙNG",
    backToJob: "← Quay lại công việc",
    topic: "Chủ đề",
    pipelineStages: "Các giai đoạn",
    finalVideo: "Video cuối cùng",
    mediaMetadata: "Thông tin media",
    audioQA: "Chất lượng âm thanh",
    qaStatus: "Trạng thái QA",
    integrity: "Tính toàn vẹn",
    provenance: "Nguồn gốc",
    resolution: "Độ phân giải",
    fps: "FPS",
    duration: "Thời lượng",
    fileSize: "Dung lượng",
    videoCodec: "Video Codec",
    audioCodec: "Audio Codec",
    sampleRate: "Tần số mẫu",
    channels: "Kênh",
    integratedLoudness: "Độ lớn tích hợp",
    truePeak: "Đỉnh thực",
    lra: "Dải động",
    checksum: "Mã kiểm tra SHA-256",
    fingerprint: "Dấu vân tay",
    renderer: "Bộ render",
    ffmpeg: "FFmpeg",
    renderProfile: "Hồ sơ render",
    masteringProfile: "Hồ sơ mastering",
    renderFailed: "Render thất bại",
    failedAtStage: "Thất bại tại giai đoạn",
    renderInProgress: "Đang render. Trang này cập nhật mỗi",
    progress: "Tiến độ",
    download: "Tải xuống MP4",
    yourBrowserNotSupport: "Trình duyệt của bạn không hỗ trợ video HTML5.",
    failedToLoadVideo: "Không thể tải video. Hãy tải xuống thay thế.",
  },

  // === Storyboard Page ===
  storyboard: {
    title: "Storyboard",
    beats: "Các beat",
    scenes: "Các cảnh",
    assets: "Tài nguyên",
    quality: "Chất lượng",
    status: "Trạng thái",
    warnings: "Cảnh báo",
    failures: "Lỗi",
    visualBeats: "Các Beat Hình ảnh",
    assetRequirements: "Yêu cầu tài nguyên",
    approve: "Chấp nhận",
    reject: "Từ chối",
    rejectionNotes: "Ghi chú từ chối (tùy chọn)",
    backToJob: "← Quay lại công việc",
    loading: "Đang tải storyboard...",
    error: "Lỗi",
    noStoryboardData: "Không có dữ liệu storyboard.",
    makeSureJobRun: "Đảm bảo công việc đã chạy giai đoạn s2_thesis và s5_storyboard.",
  },

  // === Characters Page ===
  characters: {
    title: "Nhân vật",
    allCharacters: "Tất cả nhân vật",
    preview: "Xem trước",
    qualityScore: "Điểm chất lượng",
    backToJob: "← Quay lại công việc",
    loading: "Đang tải nhân vật...",
    error: "Lỗi",
    makeSureStoryboardRun: "Hệ thống nhân vật có thể chưa chạy. Đảm bảo công việc đã chạy s5_storyboard trước.",
    characters: "Nhân vật",
    poses: "Tư thế",
    expressions: "Biểu cảm",
    selectCharacter: "Chọn một nhân vật để xem chi tiết",
    noCharactersFound: "Không tìm thấy nhân vật. Đảm bảo công việc có storyboard với yêu cầu nhân vật.",
    approve: "Chấp nhận",
    deprecate: "Loại bỏ",
    deprecationReason: "Lý do loại bỏ (tùy chọn)",
    loadingPreview: "Đang tải xem trước...",
    noPreviewAvailable: "Không có xem trước",
    identity: "Định danh",
    proportions: "Tỷ lệ",
    silhouette: "Hình dạng",
    style: "Phong cách",
    wardrobe: "Trang phục",
    poseCoverage: "Phạm vi tư thế",
    expressionCoverage: "Phạm vi biểu cảm",
    components: "Thành phần",
    animation: "Hoạt hình",
    assetFormat: "Định dạng",
    continuity: "Liên tục",
  },

  // === Assets Page ===
  assets: {
    title: "Tài nguyên",
    allAssets: "Tất cả tài nguyên",
    environments: "Môi trường",
    props: "Đạo cụ",
    registry: "Danh sách",
    totalAssets: "Tổng tài nguyên",
    global: "Toàn cục",
    backToJob: "← Quay lại công việc",
    loading: "Đang tải tài nguyên...",
    error: "Lỗi",
    makeSureAssetRun: "Hệ thống tài nguyên có thể chưa chạy.",
    noAssetsFound: "Không tìm thấy tài nguyên. Chạy hệ thống tài nguyên để tạo.",
    selectAsset: "Chọn một tài nguyên để xem chi tiết",
    approve: "Chấp nhận",
    deprecate: "Loại bỏ",
    deprecationReason: "Lý do loại bỏ (tùy chọn)",
    validate: "Xác thực",
    clickValidate: "Bấm 'Xác thực' để tính điểm chất lượng",
    URI: "URI",
    version: "Phiên bản",
    scenes: "Cảnh",
    created: "Đã tạo",
    assetRegistry: "Danh sách tài nguyên",
    projectID: "ID dự án",
    globalAssets: "Tài nguyên toàn cục",
    lastUpdated: "Cập nhật lần cuối",
    none: "Không có",
    semantic: "Ngữ nghĩa",
    composition: "Bố cục",
    resolution: "Độ phân giải",
    format: "Định dạng",
    metadata: "Siêu dữ liệu",
  },

  // === Footer ===
  footer: "Nếu gặp vấn đề, hãy liên hệ với chúng tôi.",
};

export type TranslationKey = keyof typeof vi;
