import Foundation
import PDFKit
import Vision
import AppKit

// Local-only OCR. Each page remains separate; layout and formula fidelity need review.
let url = URL(fileURLWithPath: CommandLine.arguments[1])
guard let pdf = PDFDocument(url: url), pdf.pageCount > 0, pdf.pageCount <= 100 else {
    throw NSError(domain: "conversion", code: 1, userInfo: [NSLocalizedDescriptionKey: "Unreadable PDF or page limit exceeded"])
}
var pages: [[String: Any]] = []
let selected = CommandLine.arguments.count > 2
    ? CommandLine.arguments[2].split(separator: ",").compactMap { Int($0) }
    : Array(1...pdf.pageCount)
guard !selected.isEmpty, selected.allSatisfy({ $0 >= 1 && $0 <= pdf.pageCount }),
      Set(selected).count == selected.count else { throw NSError(domain: "conversion", code: 6) }
for number in selected {
    let index = number - 1
    guard let page = pdf.page(at: index) else { throw NSError(domain: "conversion", code: 2) }
    let rect = page.bounds(for: .mediaBox)
    guard rect.width > 0, rect.height > 0 else { throw NSError(domain: "conversion", code: 3) }
    let scale = min(3.0, 3000.0 / max(rect.width, rect.height))
    let width = Int(rect.width * scale), height = Int(rect.height * scale)
    guard let context = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8,
                                  bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(),
                                  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else {
        throw NSError(domain: "conversion", code: 4)
    }
    context.setFillColor(NSColor.white.cgColor)
    context.fill(CGRect(x: 0, y: 0, width: width, height: height))
    context.scaleBy(x: scale, y: scale)
    context.translateBy(x: -rect.minX, y: -rect.minY)
    page.draw(with: .mediaBox, to: context)
    guard let image = context.makeImage() else { throw NSError(domain: "conversion", code: 5) }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["ko-KR", "en-US"]
    request.usesLanguageCorrection = false
    try VNImageRequestHandler(cgImage: image).perform([request])
    let lines = (request.results ?? []).compactMap { observation -> [String: Any]? in
        guard let candidate = observation.topCandidates(1).first else { return nil }
        return ["text": candidate.string, "confidence": candidate.confidence,
                "box": [observation.boundingBox.minX, observation.boundingBox.minY,
                        observation.boundingBox.width, observation.boundingBox.height]]
    }
    pages.append(["page": index + 1, "lines": lines])
}
let result: [String: Any] = ["engine": "macOS Vision VNRecognizeTextRequest", "pages": pages]
FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]))
