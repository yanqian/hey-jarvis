use crate::preferences::SIMPLIFIED_CHINESE;

pub fn text<'a>(locale: &str, english: &'a str, chinese: &'a str) -> &'a str {
    if locale == SIMPLIFIED_CHINESE {
        chinese
    } else {
        english
    }
}

pub fn availability(locale: &str, value: &str) -> &'static str {
    match (locale == SIMPLIFIED_CHINESE, value) {
        (false, "ready") => "Status: Ready",
        (false, "wake_listening") => "Status: Wake listening",
        (false, "busy") => "Status: Busy",
        (false, _) => "Status: Resume required",
        (true, "ready") => "状态：运行环境就绪",
        (true, "wake_listening") => "状态：正在等待唤醒",
        (true, "busy") => "状态：对话进行中",
        (true, _) => "状态：需要恢复",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn native_labels_have_complete_supported_locale_variants() {
        assert_eq!(text("en", "Settings…", "设置…"), "Settings…");
        assert_eq!(text("zh-CN", "Settings…", "设置…"), "设置…");
        for state in ["ready", "wake_listening", "busy", "resume_required"] {
            assert!(availability("en", state).starts_with("Status:"));
            assert!(availability("zh-CN", state).starts_with("状态："));
        }
    }
}
