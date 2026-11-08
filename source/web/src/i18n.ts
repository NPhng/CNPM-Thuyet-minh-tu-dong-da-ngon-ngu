export const languages=['vi','en','zh','ja','ko'] as const; export type Lang=typeof languages[number];
type Label={listen:string;activate:string;home:string;description:string;myTicket:string;heroTitle1:string;heroTitle2:string;heroDesc:string;explore:string;nearMe:string;searchPh:string};
export const labels:Record<Lang,Label>={
vi:{listen:'Nghe thuyết minh',activate:'Kích hoạt vé',home:'Trang chủ',description:'Mô tả',myTicket:'Vé của tôi',heroTitle1:'Mỗi bước chân,',heroTitle2:'một câu chuyện.',heroDesc:'Khám phá các loài động vật và nghe thuyết minh đa ngôn ngữ tại Thảo Cầm Viên Sài Gòn.',explore:'Khám phá điểm tham quan',nearMe:'Điểm gần tôi',searchPh:'Tìm tên điểm tham quan...'},
en:{listen:'Listen to guide',activate:'Activate ticket',home:'Home',description:'Description',myTicket:'My ticket',heroTitle1:'Every step,',heroTitle2:'a story.',heroDesc:'Discover the animals and listen to multilingual audio guides at Saigon Zoo and Botanical Gardens.',explore:'Explore attractions',nearMe:'Near me',searchPh:'Search attractions...'},
zh:{listen:'收听讲解',activate:'激活门票',home:'首页',description:'介绍',myTicket:'我的门票',heroTitle1:'每一步，',heroTitle2:'都是一个故事。',heroDesc:'在西贡动植物园探索动物，收听多语言讲解。',explore:'探索景点',nearMe:'离我最近',searchPh:'搜索景点...'},
ja:{listen:'音声ガイドを聞く',activate:'チケットを有効化',home:'ホーム',description:'説明',myTicket:'マイチケット',heroTitle1:'一歩ごとに、',heroTitle2:'ひとつの物語。',heroDesc:'サイゴン動植物園で動物を探索し、多言語の音声ガイドをお聞きください。',explore:'スポットを探す',nearMe:'近くのスポット',searchPh:'スポットを検索...'},
ko:{listen:'해설 듣기',activate:'티켓 활성화',home:'홈',description:'설명',myTicket:'내 티켓',heroTitle1:'한 걸음마다,',heroTitle2:'하나의 이야기.',heroDesc:'사이공 동식물원에서 동물을 만나고 다국어 오디오 해설을 들어보세요.',explore:'관람 포인트 둘러보기',nearMe:'내 주변',searchPh:'관람 포인트 검색...'}};
export const ui:Record<string,Record<Lang,string>>={
brandSub:{vi:"Sài Gòn · Thuyết minh đa ngôn ngữ",en:"Saigon · Multilingual audio guide",zh:"西贡 · 多语言讲解",ja:"サイゴン · 多言語ガイド",ko:"사이공 · 다국어 해설"},
eyebrow:{vi:"KHÁM PHÁ THIÊN NHIÊN",en:"DISCOVER NATURE",zh:"探索自然",ja:"自然を探索",ko:"자연 탐험"},
openHours:{vi:"Giờ mở cửa",en:"Opening hours",zh:"开放时间",ja:"営業時間",ko:"운영 시간"},
openHoursNote:{vi:"Thông tin cần xác nhận và cập nhật",en:"Information to be confirmed and updated",zh:"信息待确认和更新",ja:"情報は確認・更新中です",ko:"정보 확인 및 업데이트 예정"},
address:{vi:"Địa chỉ",en:"Address",zh:"地址",ja:"住所",ko:"주소"},
about:{vi:"Về sở thú",en:"About the zoo",zh:"关于动物园",ja:"動物園について",ko:"동물원 소개"},
aboutNote:{vi:"Nội dung giới thiệu chính thức cần cập nhật",en:"Official introduction to be updated",zh:"官方介绍待更新",ja:"公式の紹介文は更新予定です",ko:"공식 소개 내용 업데이트 예정"},
mapEyebrow:{vi:"BẢN ĐỒ TƯƠNG TÁC",en:"INTERACTIVE MAP",zh:"互动地图",ja:"インタラクティブマップ",ko:"인터랙티브 지도"},
whereNext:{vi:"Đi đâu tiếp nhỉ?",en:"Where to next?",zh:"接下来去哪里？",ja:"次はどこへ行く？",ko:"다음엔 어디로 갈까요?"},
whereNextDesc:{vi:"Tìm kiếm và khám phá các điểm tham quan quanh bạn.",en:"Search and explore attractions around you.",zh:"搜索并探索您周围的景点。",ja:"周辺のスポットを検索・発見しましょう。",ko:"주변 관람 포인트를 검색하고 둘러보세요."},
iAmAt:{vi:"Tôi đang ở…",en:"I am at…",zh:"我在…",ja:"現在地は…",ko:"현재 위치…"},
chooseDest:{vi:"Chọn điểm đến",en:"Choose destination",zh:"选择目的地",ja:"目的地を選ぶ",ko:"목적지 선택"},
r100:{vi:"Trong 100 m",en:"Within 100 m",zh:"100米内",ja:"100m以内",ko:"100m 이내"},
r300:{vi:"Trong 300 m",en:"Within 300 m",zh:"300米内",ja:"300m以内",ko:"300m 이내"},
r500:{vi:"Trong 500 m",en:"Within 500 m",zh:"500米内",ja:"500m以内",ko:"500m 이내"},
all:{vi:"Tất cả",en:"All",zh:"全部",ja:"すべて",ko:"전체"},
tabMap:{vi:"Bản đồ",en:"Map",zh:"地图",ja:"地図",ko:"지도"},
tabList:{vi:"Danh sách",en:"List",zh:"列表",ja:"リスト",ko:"목록"},
viewDetail:{vi:"Xem chi tiết →",en:"View details →",zh:"查看详情 →",ja:"詳細を見る →",ko:"자세히 보기 →"},
yourPos:{vi:"Vị trí bạn chọn",en:"Your selected location",zh:"您选择的位置",ja:"選択した位置",ko:"선택한 위치"},
manualNote:{vi:"Sẽ tự đổi sang GPS khi có tín hiệu.",en:"Will switch to GPS automatically when a signal is available.",zh:"有GPS信号后将自动切换。",ja:"GPS信号が取得でき次第、自動で切り替わります。",ko:"GPS 신호가 잡히면 자동으로 전환됩니다."},
needGps:{vi:"Bật định vị hoặc chọn \"Tôi đang ở…\" để xem khoảng cách.",en:"Turn on location or choose \"I am at…\" to see the distance.",zh:"请开启定位或选择\u201c我在…\u201d以查看距离。",ja:"位置情報をオンにするか「現在地は…」を選ぶと距離が表示されます。",ko:"위치를 켜거나 \"현재 위치…\"를 선택하면 거리를 볼 수 있습니다."},
noResults:{vi:"Chưa tìm thấy điểm tham quan",en:"No attractions found",zh:"未找到景点",ja:"スポットが見つかりません",ko:"관람 포인트를 찾을 수 없습니다"},
noResultsHint:{vi:"Thử đổi từ khóa hoặc bộ lọc nhé.",en:"Try a different keyword or filter.",zh:"请尝试更换关键词或筛选条件。",ja:"キーワードや条件を変えてお試しください。",ko:"다른 검색어나 필터를 사용해 보세요."},
retry:{vi:"Thử lại",en:"Try again",zh:"重试",ja:"再試行",ko:"다시 시도"},
footer:{vi:"© Thảo Cầm Viên Sài Gòn · Cùng khám phá và bảo tồn thiên nhiên",en:"© Saigon Zoo and Botanical Gardens · Explore and protect nature together",zh:"© 西贡动植物园 · 一起探索和保护自然",ja:"© サイゴン動植物園 · 自然を一緒に探索し守りましょう",ko:"© 사이공 동식물원 · 함께 탐험하고 자연을 보호해요"},
gpsUnsupported:{vi:"Thiết bị chưa hỗ trợ định vị. Hãy chọn \"Tôi đang ở…\" để tiếp tục.",en:"Your device does not support location. Choose \"I am at…\" to continue.",zh:"您的设备不支持定位。请选择\u201c我在…\u201d继续。",ja:"この端末は位置情報に対応していません。「現在地は…」を選んで続けてください。",ko:"이 기기는 위치 확인을 지원하지 않습니다. \"현재 위치…\"를 선택해 계속하세요."},
gpsOk:{vi:"Đã xác định vị trí của bạn.",en:"Your location has been found.",zh:"已确定您的位置。",ja:"現在地を取得しました。",ko:"현재 위치를 확인했습니다."},
gpsFail:{vi:"Chưa lấy được vị trí GPS. Bạn có thể chọn \"Tôi đang ở…\" bên dưới.",en:"Could not get GPS location. You can choose \"I am at…\" below.",zh:"无法获取GPS位置。您可以在下方选择\u201c我在…\u201d。",ja:"GPS位置を取得できませんでした。下の「現在地は…」から選べます。",ko:"GPS 위치를 가져올 수 없습니다. 아래에서 \"현재 위치…\"를 선택할 수 있습니다."},
gpsNeed:{vi:"Hãy bật định vị hoặc chọn \"Tôi đang ở…\" để tìm điểm gần bạn.",en:"Turn on location or choose \"I am at…\" to find places near you.",zh:"请开启定位或选择\u201c我在…\u201d以查找附近景点。",ja:"位置情報をオンにするか「現在地は…」を選ぶと近くのスポットを探せます。",ko:"위치를 켜거나 \"현재 위치…\"를 선택하면 주변 포인트를 찾을 수 있습니다."},
cat_tien_ich:{vi:"Tiện ích",en:"Facilities",zh:"设施",ja:"施設",ko:"편의시설"},
cat_chim:{vi:"Chim",en:"Birds",zh:"鸟类",ja:"鳥類",ko:"조류"},
cat_thu_an_thit:{vi:"Thú ăn thịt",en:"Carnivores",zh:"食肉动物",ja:"肉食動物",ko:"육식동물"},
cat_thu_an_co:{vi:"Thú ăn cỏ",en:"Herbivores",zh:"食草动物",ja:"草食動物",ko:"초식동물"},
cat_bo_sat_luong_cu:{vi:"Bò sát & lưỡng cư",en:"Reptiles & amphibians",zh:"爬行与两栖动物",ja:"爬虫類・両生類",ko:"파충류·양서류"},
cat_linh_truong:{vi:"Linh trưởng",en:"Primates",zh:"灵长类",ja:"霊長類",ko:"영장류"},
backAll:{vi:"Tất cả điểm tham quan",en:"All attractions",zh:"所有景点",ja:"すべてのスポット",ko:"모든 관람 포인트"},
photoTag:{vi:"Khám phá thiên nhiên",en:"Discover nature",zh:"探索自然",ja:"自然を探索",ko:"자연 탐험"},
noDesc:{vi:"Nội dung giới thiệu cho điểm tham quan này đang được cập nhật.",en:"The introduction for this attraction is being updated.",zh:"该景点的介绍正在更新中。",ja:"このスポットの紹介文は更新中です。",ko:"이 관람 포인트의 소개는 업데이트 중입니다."},
lockedHint:{vi:"Cần vé để nghe, kích hoạt ở đây.",en:"A ticket is required to listen. Activate it here.",zh:"收听需要门票，请在此激活。",ja:"音声を聞くにはチケットが必要です。こちらで有効化してください。",ko:"들으려면 티켓이 필요합니다. 여기서 활성화하세요."},
lockedLink:{vi:"Kích hoạt vé ngay →",en:"Activate ticket now →",zh:"立即激活门票 →",ja:"今すぐチケットを有効化 →",ko:"지금 티켓 활성화 →"},
audioTitle:{vi:"Thuyết minh âm thanh",en:"Audio guide",zh:"语音讲解",ja:"音声ガイド",ko:"오디오 해설"},
audioPreparing:{vi:"Đang chuẩn bị audio…",en:"Preparing audio…",zh:"正在准备音频…",ja:"音声を準備中…",ko:"오디오 준비 중…"},
audioReady:{vi:"Nghe giới thiệu về điểm tham quan này.",en:"Listen to the introduction to this attraction.",zh:"收听该景点的介绍。",ja:"このスポットの紹介を聞きましょう。",ko:"이 관람 포인트의 소개를 들어보세요."},
audioHint:{vi:"Nhấn phát để nghe",en:"Press play to listen",zh:"点击播放收听",ja:"再生ボタンを押して聞く",ko:"재생을 눌러 들어보세요"},
loading:{vi:"Đang tải…",en:"Loading…",zh:"加载中…",ja:"読み込み中…",ko:"불러오는 중…"},
audioErr502:{vi:"Dịch vụ giọng nói đang gặp sự cố. Hãy thử lại.",en:"The voice service is having problems. Please try again.",zh:"语音服务出现故障，请重试。",ja:"音声サービスに問題が発生しています。もう一度お試しください。",ko:"음성 서비스에 문제가 있습니다. 다시 시도해 주세요."},
ticketEyebrow:{vi:"THẺ DU KHÁCH",en:"VISITOR PASS",zh:"游客证",ja:"来園者パス",ko:"방문객 카드"},
ticketOk:{vi:"Vé đã kích hoạt trên thiết bị này.",en:"Ticket activated on this device.",zh:"门票已在此设备上激活。",ja:"このデバイスでチケットが有効化されています。",ko:"이 기기에서 티켓이 활성화되었습니다."},
expires:{vi:"Hết hạn:",en:"Expires:",zh:"有效期至：",ja:"有効期限：",ko:"만료:"},
ticketNone:{vi:"Bạn chưa kích hoạt vé. Bạn vẫn có thể xem tất cả điểm tham quan.",en:"You have not activated a ticket. You can still browse all attractions.",zh:"您尚未激活门票，仍可浏览所有景点。",ja:"チケットは未有効化です。すべてのスポットは引き続き閲覧できます。",ko:"티켓을 활성화하지 않았습니다. 모든 관람 포인트는 계속 볼 수 있습니다."},
enterOther:{vi:"Nhập mã vé khác",en:"Enter another ticket code",zh:"输入其他票码",ja:"別のチケットコードを入力",ko:"다른 티켓 코드 입력"},
logoutConfirm:{vi:"Đăng xuất vé khỏi máy này? Bạn cần nhập lại mã vé để nghe tiếp.",en:"Remove the ticket from this device? You will need to enter the code again to keep listening.",zh:"从此设备移除门票？继续收听需要重新输入票码。",ja:"このデバイスからチケットを削除しますか？続けて聞くにはコードの再入力が必要です。",ko:"이 기기에서 티켓을 삭제할까요? 계속 들으려면 코드를 다시 입력해야 합니다."},
logoutBtn:{vi:"Đăng xuất vé khỏi máy này",en:"Remove ticket from this device",zh:"从此设备移除门票",ja:"このデバイスからチケットを削除",ko:"이 기기에서 티켓 삭제"},
exploreThis:{vi:"Khám phá điểm tham quan này.",en:"Explore this attraction.",zh:"探索这个景点。",ja:"このスポットを探索しましょう。",ko:"이 관람 포인트를 둘러보세요."},
// --- Activate ---
backHome:{vi:"← Về trang chủ",en:"← Back to home",zh:"← 返回首页",ja:"← ホームへ戻る",ko:"← 홈으로 돌아가기"},
unlockEyebrow:{vi:"MỞ KHÓA TRẢI NGHIỆM",en:"UNLOCK YOUR EXPERIENCE",zh:"解锁体验",ja:"体験をアンロック",ko:"체험 잠금 해제"},
activateTitle:{vi:"Kích hoạt vé tham quan",en:"Activate your ticket",zh:"激活参观门票",ja:"チケットを有効化する",ko:"관람 티켓 활성화"},
activateDesc:{vi:"Nhập mã trên vé của bạn để mở khóa thuyết minh âm thanh.",en:"Enter the code on your ticket to unlock the audio guide.",zh:"输入票面上的代码以解锁语音讲解。",ja:"チケットに記載のコードを入力して音声ガイドをアンロックしてください。",ko:"티켓의 코드를 입력하여 오디오 해설을 잠금 해제하세요."},
ticketCode:{vi:"Mã vé",en:"Ticket code",zh:"票码",ja:"チケットコード",ko:"티켓 코드"},
ticketCodePh:{vi:"VD: TCV-ABC123",en:"e.g. TCV-ABC123",zh:"例：TCV-ABC123",ja:"例：TCV-ABC123",ko:"예: TCV-ABC123"},
scanQr:{vi:"Quét mã QR",en:"Scan QR code",zh:"扫描二维码",ja:"QRコードをスキャン",ko:"QR 코드 스캔"},
activating:{vi:"Đang kích hoạt…",en:"Activating…",zh:"正在激活…",ja:"有効化中…",ko:"활성화 중…"},
oneDeviceNote:{vi:"Vé chỉ có thể nghe trên một thiết bị tại một thời điểm.",en:"The ticket can only be used on one device at a time.",zh:"门票同一时间只能在一台设备上使用。",ja:"チケットは同時に1台のデバイスでのみ使用できます。",ko:"티켓은 한 번에 한 기기에서만 사용할 수 있습니다."},
successTitle:{vi:"Kích hoạt thành công!",en:"Activation successful!",zh:"激活成功！",ja:"有効化完了！",ko:"활성화 성공!"},
successDesc:{vi:"Vé đã được liên kết với thiết bị này. Chúc bạn có chuyến tham quan vui vẻ.",en:"The ticket has been linked to this device. Enjoy your visit!",zh:"门票已与此设备关联，祝您参观愉快。",ja:"チケットがこのデバイスに紐づけられました。楽しい観覧を！",ko:"티켓이 이 기기에 연결되었습니다. 즐거운 관람 되세요."},
goHome:{vi:"Về trang chủ",en:"Go to home",zh:"返回首页",ja:"ホームへ",ko:"홈으로 이동"},
goListen:{vi:"Đi nghe thuyết minh",en:"Go listen to the guide",zh:"去听讲解",ja:"音声ガイドを聞く",ko:"해설 듣기"},
switchTitle:{vi:"Chuyển vé sang thiết bị này?",en:"Transfer ticket to this device?",zh:"将门票转移到此设备？",ja:"このデバイスにチケットを転送しますか？",ko:"이 기기로 티켓을 이전할까요?"},
switchDesc:{vi:"Vé này đã dùng ở máy khác. Chuyển sang máy này? Máy cũ sẽ không nghe được nữa.",en:"This ticket is already in use on another device. Transfer to this one? The other device will lose access.",zh:"此门票已在其他设备上使用。转移到此设备？原设备将无法继续使用。",ja:"このチケットは別のデバイスで使用中です。このデバイスに転送しますか？元のデバイスでは使えなくなります。",ko:"이 티켓은 다른 기기에서 사용 중입니다. 이 기기로 이전할까요? 기존 기기에서는 더 이상 들을 수 없습니다."},
cancel:{vi:"Hủy",en:"Cancel",zh:"取消",ja:"キャンセル",ko:"취소"},
confirmSwitch:{vi:"Đồng ý chuyển",en:"Confirm transfer",zh:"确认转移",ja:"転送する",ko:"이전 확인"},
replaceTitle:{vi:"Thay vé đang sử dụng?",en:"Replace current ticket?",zh:"替换当前门票？",ja:"現在のチケットを交換しますか？",ko:"현재 티켓을 교체할까요?"},
replaceDesc:{vi:"Bạn đang có vé còn hạn đến {date}. Bạn có muốn thay bằng vé mới không?",en:"You have an active ticket valid until {date}. Do you want to replace it with the new one?",zh:"您目前有一张有效期至 {date} 的门票，是否替换为新票？",ja:"有効期限 {date} のチケットが使用中です。新しいチケットに交換しますか？",ko:"{date}까지 유효한 티켓이 있습니다. 새 티켓으로 교체하시겠습니까?"},
confirmReplace:{vi:"Đồng ý thay vé",en:"Confirm replacement",zh:"确认替换",ja:"交換する",ko:"교체 확인"},
// --- Errors ---
errTicketInvalid:{vi:"Mã vé không đúng",en:"Invalid ticket code",zh:"票码不正确",ja:"チケットコードが正しくありません",ko:"티켓 코드가 올바르지 않습니다"},
errTicketExpired:{vi:"Vé đã hết hạn",en:"Ticket has expired",zh:"门票已过期",ja:"チケットの有効期限が切れています",ko:"티켓이 만료되었습니다"},
errTooMany:{vi:"Thử quá nhiều lần, vui lòng đợi ít phút",en:"Too many attempts, please wait a few minutes",zh:"尝试次数过多，请稍候片刻",ja:"試行回数が多すぎます。しばらくお待ちください",ko:"시도 횟수가 너무 많습니다. 잠시 후 다시 시도해 주세요"},
errSession:{vi:"Phiên đăng nhập hoặc vé không còn hiệu lực.",en:"Your session or ticket is no longer valid.",zh:"您的登录会话或门票已失效。",ja:"セッションまたはチケットが無効です。",ko:"세션 또는 티켓이 더 이상 유효하지 않습니다."},
errForbidden:{vi:"Bạn không có quyền thực hiện thao tác này.",en:"You do not have permission to perform this action.",zh:"您没有权限执行此操作。",ja:"この操作を行う権限がありません。",ko:"이 작업을 수행할 권한이 없습니다."},
errGeneric:{vi:"Đã xảy ra lỗi. Vui lòng thử lại.",en:"An error occurred. Please try again.",zh:"发生错误，请重试。",ja:"エラーが発生しました。もう一度お試しください。",ko:"오류가 발생했습니다. 다시 시도해 주세요."},
ticketRevoked:{vi:"Vé không còn hiệu lực hoặc đã được chuyển sang thiết bị khác. Vui lòng nhập lại mã vé.",en:"The ticket is no longer valid or has been transferred to another device. Please re-enter the ticket code.",zh:"门票已失效或已转移到其他设备，请重新输入票码。",ja:"チケットは無効になったか、他のデバイスに転送されました。チケットコードを再入力してください。",ko:"티켓이 더 이상 유효하지 않거나 다른 기기로 이전되었습니다. 티켓 코드를 다시 입력해 주세요."},
enterCode:{vi:"Nhập mã vé",en:"Enter ticket code",zh:"输入票码",ja:"チケットコードを入力",ko:"티켓 코드 입력"},
closeNotice:{vi:"Đóng thông báo",en:"Close notice",zh:"关闭通知",ja:"通知を閉じる",ko:"알림 닫기"},
close:{vi:"Đóng",en:"Close",zh:"关闭",ja:"閉じる",ko:"닫기"},
// --- QR scanner ---
scanTitle:{vi:"Quét mã QR trên vé",en:"Scan QR code on ticket",zh:"扫描票上的二维码",ja:"チケットのQRコードをスキャン",ko:"티켓의 QR 코드 스캔"},
scanHint:{vi:"Đưa mã QR vào giữa khung hình.",en:"Place the QR code within the frame.",zh:"将二维码置于框内。",ja:"QRコードをフレームの中央に合わせてください。",ko:"QR 코드를 프레임 안에 맞춰 주세요."},
scanStarting:{vi:"Đang khởi động camera…",en:"Starting camera…",zh:"正在启动摄像头…",ja:"カメラを起動中…",ko:"카메라 시작 중…"},
scanClose:{vi:"Đóng và nhập mã thủ công",en:"Close and enter code manually",zh:"关闭并手动输入票码",ja:"閉じて手動でコードを入力",ko:"닫고 수동으로 코드 입력"},
scanCloseAria:{vi:"Đóng trình quét QR",en:"Close QR scanner",zh:"关闭二维码扫描器",ja:"QRスキャナーを閉じる",ko:"QR 스캐너 닫기"},
scanInvalid:{vi:"QR không hợp lệ hoặc không chứa mã kích hoạt. Hãy thử lại hoặc nhập mã vé thủ công.",en:"Invalid QR or no activation code found. Try again or enter the ticket code manually.",zh:"二维码无效或不含激活码，请重试或手动输入票码。",ja:"QRが無効か有効化コードが含まれていません。再試行するか、チケットコードを手動で入力してください。",ko:"유효하지 않은 QR이거나 활성화 코드가 없습니다. 다시 시도하거나 티켓 코드를 직접 입력해 주세요."},
scanErrEmbedded:{vi:"Bạn đang mở trang trong trình duyệt nhúng. Hãy mở bằng Safari hoặc Chrome, hoặc nhập mã vé thủ công.",en:"You are using an in-app browser. Please open in Safari or Chrome, or enter the ticket code manually.",zh:"您正在使用内嵌浏览器，请用Safari或Chrome打开，或手动输入票码。",ja:"アプリ内ブラウザを使用中です。SafariまたはChromeで開くか、チケットコードを手動で入力してください。",ko:"인앱 브라우저를 사용 중입니다. Safari 또는 Chrome으로 열거나 티켓 코드를 직접 입력해 주세요."},
scanErrHttps:{vi:"Camera cần HTTPS hoặc localhost. Hãy nhập mã vé thủ công.",en:"Camera requires HTTPS or localhost. Please enter the ticket code manually.",zh:"相机需要HTTPS或localhost，请手动输入票码。",ja:"カメラにはHTTPSまたはlocalhostが必要です。チケットコードを手動で入力してください。",ko:"카메라는 HTTPS 또는 localhost가 필요합니다. 티켓 코드를 직접 입력해 주세요."},
scanErrUnsupported:{vi:"Trình duyệt không hỗ trợ camera. Hãy mở bằng Safari hoặc Chrome, hoặc nhập mã thủ công.",en:"Your browser does not support camera access. Please open in Safari or Chrome, or enter the code manually.",zh:"浏览器不支持摄像头，请用Safari或Chrome打开，或手动输入票码。",ja:"お使いのブラウザはカメラに対応していません。SafariまたはChromeで開くか、手動でコードを入力してください。",ko:"브라우저가 카메라를 지원하지 않습니다. Safari 또는 Chrome으로 열거나 코드를 직접 입력해 주세요."},
scanErrOpen:{vi:"Không mở được camera. Hãy cấp quyền camera, mở bằng Safari/Chrome hoặc nhập mã vé thủ công.",en:"Could not open camera. Please allow camera access, open in Safari/Chrome, or enter the ticket code manually.",zh:"无法打开摄像头，请授权相机权限、使用Safari/Chrome打开，或手动输入票码。",ja:"カメラを開けません。カメラの権限を許可するか、Safari/Chromeで開くか、チケットコードを手動で入力してください。",ko:"카메라를 열 수 없습니다. 카메라 권한을 허용하거나 Safari/Chrome으로 열거나 티켓 코드를 직접 입력해 주세요."},
// --- Aria-label guest ---
ariaIAmAt:{vi:"Tôi đang ở",en:"I am at",zh:"我在",ja:"現在地",ko:"현재 위치"},
ariaDest:{vi:"Chọn điểm đến",en:"Choose destination",zh:"选择目的地",ja:"目的地を選ぶ",ko:"목적지 선택"},
ariaRadius:{vi:"Bán kính tìm kiếm",en:"Search radius",zh:"搜索半径",ja:"検索範囲",ko:"검색 반경"},
// --- Error keys (không hardcode tiếng Việt trong client.ts) ---
errNetwork:{vi:"Không thể kết nối máy chủ. Hãy kiểm tra kết nối mạng.",en:"Cannot connect to the server. Please check your network.",zh:"无法连接服务器，请检查网络连接。",ja:"サーバーに接続できません。ネットワークを確認してください。",ko:"서버에 연결할 수 없습니다. 네트워크를 확인해 주세요."},
errNotFound:{vi:"Không tìm thấy nội dung này.",en:"Content not found.",zh:"找不到该内容。",ja:"コンテンツが見つかりません。",ko:"콘텐츠를 찾을 수 없습니다."},
errInvalidInput:{vi:"Dữ liệu gửi lên không hợp lệ.",en:"The submitted data is invalid.",zh:"提交的数据无效。",ja:"送信されたデータが無効です。",ko:"제출한 데이터가 올바르지 않습니다."},
errUnavailable:{vi:"Dịch vụ tạm thời không khả dụng. Hãy thử lại sau.",en:"Service temporarily unavailable. Please try again later.",zh:"服务暂时不可用，请稍后再试。",ja:"サービスが一時的に利用できません。後でもう一度お試しください。",ko:"서비스를 일시적으로 사용할 수 없습니다. 나중에 다시 시도해 주세요."},
errNoTranslation:{vi:"Chưa có thuyết minh cho ngôn ngữ này.",en:"No audio guide available for this language.",zh:"此语言暂无讲解内容。",ja:"この言語の音声ガイドはまだありません。",ko:"이 언어의 오디오 해설이 아직 없습니다."},
ticketExpired:{vi:"Vé của bạn đã hết hạn. Vui lòng kích hoạt vé mới.",en:"Your ticket has expired. Please activate a new ticket.",zh:"您的门票已过期，请激活新门票。",ja:"チケットの有効期限が切れました。新しいチケットを有効化してください。",ko:"티켓이 만료되었습니다. 새 티켓을 활성화해 주세요."},
};
export const T=(k:string,l:Lang):string=>{
  const entry=ui[k];
  if(import.meta.env.DEV){
    if(!entry) console.warn(`[i18n] missing key: "${k}"`);
    else if(entry[l]===undefined) console.warn(`[i18n] missing lang "${l}" for key "${k}"`);
  }
  return entry?.[l]??k;
};
export const catName=(id:string,l:Lang)=>ui['cat_'+id]?.[l]??id;
/** errorText(e, lang) – map ApiError sang chuỗi đã dịch; không bao giờ hiện tiếng Việt khi lang≠vi */
export function errorText(e:unknown,l:Lang):string{
  if(e instanceof Error && 'status' in e){
    const ae=e as {status:number;code?:string};
    if(ae.status===0)      return T('errNetwork',l);
    if(ae.status===401)    return T('errSession',l);
    if(ae.status===403)    return T('errForbidden',l);
    if(ae.status===404)    return T('errNotFound',l);
    if(ae.status===422)    return T('errInvalidInput',l);
    if(ae.status===429)    return T('errTooMany',l);
    if(ae.status===502||ae.status===503) return T('errUnavailable',l);
    if(ae.code==='no_translation') return T('errNoTranslation',l);
  }
  return T('errGeneric',l);
}
export const LOCALES:Record<Lang,string>={vi:'vi-VN',en:'en-US',zh:'zh-CN',ja:'ja-JP',ko:'ko-KR'};
