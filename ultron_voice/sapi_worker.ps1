param(
    [Parameter(Mandatory=$true)][string] $TextPath,
    [Parameter(Mandatory=$true)][string] $OutPath,
    [Parameter(Mandatory=$true)][string] $VoiceName,
    [Parameter(Mandatory=$true)][string] $Language
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $installed = @($voice.GetInstalledVoices() | Where-Object {
        $_.Enabled -and $_.VoiceInfo.Name -ceq $VoiceName -and
        $_.VoiceInfo.Culture.Name -eq $Language
    })
    if ($installed.Count -ne 1) { throw "SAPI_VOICE_NOT_INSTALLED" }
    $text = [System.IO.File]::ReadAllText($TextPath, [System.Text.Encoding]::UTF8)
    if ([string]::IsNullOrWhiteSpace($text)) { throw "SAPI_TEXT_EMPTY" }
    $voice.SelectVoice($VoiceName)
    $format = [System.Speech.AudioFormat.SpeechAudioFormatInfo]::new(
        16000,
        [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
        [System.Speech.AudioFormat.AudioChannel]::Mono
    )
    $voice.SetOutputToWaveFile($OutPath, $format)
    $voice.Speak($text)
}
finally {
    $voice.Dispose()
}
