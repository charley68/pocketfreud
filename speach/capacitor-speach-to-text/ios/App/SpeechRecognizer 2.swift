import Foundation
import Capacitor
import Speech

@objc(SpeechRecognizer)
public class SpeechRecognizer: CAPPlugin {
  private let audioEngine = AVAudioEngine()
  private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
  private var recognitionTask: SFSpeechRecognitionTask?
  private let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))

  @objc func start(_ call: CAPPluginCall) {
    SFSpeechRecognizer.requestAuthorization { authStatus in
      if authStatus != .authorized {
        call.reject("Speech recognition not authorized")
        return
      }

      DispatchQueue.main.async {
        do {
          try self.startListening(call)
        } catch {
          call.reject("Failed to start recognition: \(error.localizedDescription)")
        }
      }
    }
  }

  private func startListening(_ call: CAPPluginCall) throws {
    let node = audioEngine.inputNode

    recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
    guard let recognitionRequest = recognitionRequest else {
      call.reject("Unable to create recognition request")
      return
    }

    recognitionRequest.shouldReportPartialResults = true

    recognitionTask = speechRecognizer?.recognitionTask(with: recognitionRequest) { result, error in
      if let result = result {
        self.notifyListeners("onSpeech", data: [
          "transcript": result.bestTranscription.formattedString
        ], retainUntilConsumed: true)
      }
      if let error = error {
        print("Recognition error: \(error.localizedDescription)")
      }
    }

    let recordingFormat = node.outputFormat(forBus: 0)
    node.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { (buffer, _) in
      self.recognitionRequest?.append(buffer)
    }

    audioEngine.prepare()
    try audioEngine.start()

    call.resolve()
  }

  @objc func stop(_ call: CAPPluginCall) {
    audioEngine.stop()
    audioEngine.inputNode.removeTap(onBus: 0)
    recognitionRequest?.endAudio()
    recognitionRequest = nil
    recognitionTask?.cancel()
    call.resolve()
  }
}

