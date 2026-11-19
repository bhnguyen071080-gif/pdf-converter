"""Từ điển thuật ngữ kỹ thuật thiết bị cảng biển (gốc -> tiếng Việt). Điểm khởi đầu, người dùng bổ sung thêm trên giao diện.
Khi dịch sang tiếng Việt, thuật ngữ trong từ điển được thay trước khi gửi dịch để không bị dịch sai nghĩa."""

EN_VI = {
    "ship-to-shore crane": "cẩu bờ (QC)", "ship to shore crane": "cẩu bờ (QC)", "STS crane": "cẩu bờ (QC)",
    "quay crane": "cẩu bờ (QC)", "rubber tyred gantry crane": "cẩu khung bánh lốp (RTG)",
    "rubber tired gantry crane": "cẩu khung bánh lốp (RTG)", "RTG crane": "cẩu khung bánh lốp (RTG)",
    "rail mounted gantry crane": "cẩu khung bánh ray (RMG)", "mobile harbour crane": "cẩu di động bến cảng",
    "reach stacker": "xe nâng container (reach stacker)", "terminal tractor": "xe đầu kéo nội bộ (Tukan)",
    "yard tractor": "xe đầu kéo nội bộ (Tukan)", "forklift truck": "xe nâng hàng", "forklift": "xe nâng hàng",
    "empty container handler": "xe nâng container rỗng", "top lifter": "xe nâng container phía trên",
    "spreader": "khung cẩu (spreader)", "twist lock": "khóa xoay (twistlock)", "twistlock": "khóa xoay (twistlock)",
    "headblock": "khối đầu cẩu", "hoist": "cơ cấu nâng", "trolley": "xe con", "gantry": "cổng cẩu",
    "boom": "cần", "wire rope": "cáp thép", "steel wire rope": "cáp thép", "sheave": "puly", "pulley": "puly",
    "winch": "tời", "drum": "tang cuốn cáp", "brake": "phanh", "gearbox": "hộp giảm tốc",
    "speed reducer": "hộp giảm tốc", "coupling": "khớp nối", "bearing": "vòng bi", "shaft": "trục",
    "hydraulic cylinder": "xi lanh thủy lực", "hydraulic pump": "bơm thủy lực", "hydraulic oil": "dầu thủy lực",
    "hydraulic system": "hệ thống thủy lực", "electric motor": "động cơ điện", "diesel engine": "động cơ diesel",
    "frequency converter": "biến tần", "inverter": "biến tần", "limit switch": "công tắc hành trình",
    "proximity switch": "cảm biến tiệm cận", "encoder": "bộ mã hóa vòng quay (encoder)",
    "circuit breaker": "áp tô mát", "contactor": "công tắc tơ", "relay": "rơ le", "transformer": "máy biến áp",
    "slip ring": "vành trượt", "cable reel": "tang cuốn cáp điện", "festoon": "hệ thống cáp treo (festoon)",
    "overload": "quá tải", "anti-collision": "chống va chạm", "anti-sway": "chống đung đưa",
    "emergency stop": "dừng khẩn cấp", "safe working load": "tải trọng làm việc an toàn (SWL)",
    "SWL": "tải trọng làm việc an toàn (SWL)", "rated load": "tải trọng định mức", "rated capacity": "sức nâng định mức",
    "wind speed": "tốc độ gió", "lubrication": "bôi trơn", "grease": "mỡ bôi trơn", "gear oil": "dầu hộp số",
    "maintenance": "bảo dưỡng", "preventive maintenance": "bảo dưỡng phòng ngừa", "repair": "sửa chữa",
    "overhaul": "đại tu", "inspection": "kiểm tra", "spare parts": "phụ tùng thay thế", "spare part": "phụ tùng thay thế",
    "fuel filter": "lọc nhiên liệu", "air filter": "lọc gió", "oil filter": "lọc dầu", "coolant": "nước làm mát",
    "radiator": "két nước", "alternator": "máy phát điện xe", "starter motor": "mô tơ đề", "battery": "ắc quy",
    "tyre": "lốp", "tire": "lốp", "axle": "cầu xe", "steering": "hệ thống lái", "turbocharger": "tăng áp",
    "container": "container", "lashing": "chằng buộc", "fender": "đệm va", "bollard": "cọc neo tàu",
    "berth": "cầu bến", "quay": "cầu cảng", "yard": "bãi container", "terminal": "bến cảng",
    "torque": "mô men xoắn", "bolt": "bu lông", "nut": "đai ốc", "washer": "vòng đệm", "gasket": "gioăng",
    "seal": "phớt", "o-ring": "gioăng chữ O", "valve": "van", "nozzle": "vòi phun", "injector": "kim phun",
}

DE_VI = {
    "Containerbrücke": "cẩu bờ (QC)", "Portalkran": "cẩu khung", "Reifenportalkran": "cẩu khung bánh lốp (RTG)",
    "Gabelstapler": "xe nâng hàng", "Containerstapler": "xe nâng container", "Spreader": "khung cẩu (spreader)",
    "Drahtseil": "cáp thép", "Seilrolle": "puly", "Seiltrommel": "tang cuốn cáp", "Hubwerk": "cơ cấu nâng",
    "Laufkatze": "xe con", "Ausleger": "cần", "Bremse": "phanh", "Getriebe": "hộp giảm tốc", "Kupplung": "khớp nối",
    "Wälzlager": "vòng bi", "Lager": "vòng bi", "Welle": "trục", "Hydraulikzylinder": "xi lanh thủy lực",
    "Hydraulikpumpe": "bơm thủy lực", "Hydrauliköl": "dầu thủy lực", "Elektromotor": "động cơ điện",
    "Frequenzumrichter": "biến tần", "Endschalter": "công tắc hành trình", "Überlast": "quá tải",
    "Not-Aus": "dừng khẩn cấp", "Wartung": "bảo dưỡng", "Instandsetzung": "sửa chữa", "Ersatzteil": "phụ tùng thay thế",
    "Ersatzteile": "phụ tùng thay thế", "Schmierung": "bôi trơn", "Schmierfett": "mỡ bôi trơn", "Tragfähigkeit": "tải trọng nâng",
    "Dichtung": "gioăng", "Schraube": "bu lông", "Mutter": "đai ốc", "Ventil": "van",
}

DEFAULT = {"en": EN_VI, "de": DE_VI}
