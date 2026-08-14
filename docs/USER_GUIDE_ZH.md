# Hey Jarvis 用户安装与使用说明

Hey Jarvis 是一个面向 Apple Silicon Mac 的本地优先语音助手。它在本地等待
“Hey Jarvis”，被唤醒后才把对话音频交给 OpenAI。应用采用 BYOK（Bring Your
Own Key）：用户使用自己的 OpenAI API Key，Key 由 macOS Keychain 保存。

> 当前版本是 `0.1.0 INTERNAL-UNSIGNED` 内部测试版本，仅适合明确知情的
> 受信用户。它没有 Developer ID 签名，也没有 notarization，不是公开下载版。

## 使用前确认

- Apple Silicon Mac（M 系列）
- macOS 14 或更高版本
- 一个自己的 OpenAI API Key
- 互联网连接和可用的麦克风
- OpenAI API 使用会计费，费用由 Key 所属账户承担

应用不会把共享 Key 写进安装包，也不会把 Key 放进网页、命令行参数、日志、
录音、转写或 support bundle。

## 安装应用

1. 从项目所有者处取得 `Hey-Jarvis-0.1.0-INTERNAL-UNSIGNED-arm64.dmg` 和对应
   的 SHA-256 校验值。
2. 在终端执行校验：

   ```bash
   shasum -a 256 Hey-Jarvis-0.1.0-INTERNAL-UNSIGNED-arm64.dmg
   ```

   只在结果与所有者提供的校验值一致时继续。
3. 打开 DMG，阅读其中的 `INTERNAL-UNSIGNED.txt`，把 **Hey Jarvis** 拖到
   **Applications**。
4. 从 **Applications** 启动应用。如果 macOS 阻止启动，打开
   **System Settings → Privacy & Security**，确认来源可信后选择 **Open Anyway**。
   不要关闭 Gatekeeper，也不要执行 `xattr` 绕过隔离。

## 首次设置

1. 在 **Settings → API Keys** 中输入自己的 OpenAI API Key；如需股票报价，
   可另外配置 Finnhub Key。保存后 Key 只显示为已配置状态。
2. 阅读隐私和 API 费用说明。
3. 在 **System Settings → Privacy & Security → Microphone** 中允许
   **Hey Jarvis** 使用麦克风。
4. 回到应用，点击 **Check microphone & start**。
5. 首次启动 Realtime 页面时，点击 **Enable voice assistant**。

如果麦克风检查失败，先关闭其他可能占用麦克风的应用，再从设置页重新检查。
需要更换或删除 Key 时，应用会安全暂停当前运行，并显示恢复操作；不要在运行
中的旧会话继续测试。

## 日常使用

应用进入 **Wake listening** 后：

1. 说 “Hey Jarvis”。
2. 听到 acknowledgement 后提出问题。
3. 在同一段 Realtime 对话中可以直接追问，不需要重复唤醒词。
4. 可以用自然的第二个问题打断较长回答。
5. 说 “再见” 结束当前会话；应用释放 WebView 音频并恢复本地唤醒监听。

支持的示例包括普通知识问答、时间、天气、汇率、计算，以及在配置 Finnhub
Key 后查询股票报价。Smart Speaker Mode 允许在 Mac 锁屏或显示器关闭后继续
保持唤醒能力，但实际表现取决于 macOS、电源、麦克风和当前设备状态。

## 设置、诊断与退出

- 从主窗口右上角、菜单栏图标或 `⌘,` 打开 Settings。
- **应用并完成** 是 Settings 唯一的完成操作。没有影响运行时的更改时，它只关闭 Settings；如果某项设置安全暂停了已就绪或正在监听的 sidecar，它会先恢复原状态，确认成功后再关闭；如果打开 Settings 时助手本来就未运行，它不会擅自启动。
- **Privacy & Diagnostics → Export support bundle** 可导出脱敏支持包；其中
  不包含 Key、原始音频或转写内容。
- **Clear diagnostics** 只清除当前诊断历史，不会删除已经导出的支持包。
- 从菜单栏退出应用，确认唤醒监听和 sidecar 都停止；需要时重新启动一次。

## 更新、回滚与卸载

这是手动更新版本。退出应用后，先保留旧 DMG，再校验并安装新的
`INTERNAL-UNSIGNED` DMG。出现问题时，将新版本移到废纸篓，恢复旧 DMG，
不要同时运行两个版本。

卸载步骤：退出菜单栏应用，把 `/Applications/Hey Jarvis.app` 移到废纸篓。
如果不再需要本地设置和日志，可另外删除：

```text
~/Library/Application Support/com.heyjarvis.desktop
```

删除前请确认不需要其中的本地状态；Keychain 中的凭据应先从应用 Settings
中删除。

## 遇到问题时提供什么

请提供 macOS 版本、Mac 架构、应用版本、DMG 校验结果、发生问题的步骤、是否
恢复成功，以及脱敏 support bundle。不要发送 API Key、录音、转写、完整姓名、
邮箱或设备序列号。

更详细的故障排查见 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)，内部测试边界
见 [INTERNAL_MAC_APP_TESTING.md](INTERNAL_MAC_APP_TESTING.md)。
