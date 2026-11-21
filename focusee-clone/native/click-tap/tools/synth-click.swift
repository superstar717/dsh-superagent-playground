// Test tool: posts N real left-clicks at a screen position via CGEventPost.
// Used ONLY by the helper's standalone verification (the shell that builds it
// already holds the accessibility grant through its parent process chain).
//
//   synth-click <x> <y> [clicks=1] [downMs=60]
//
// x/y are global display coordinates (top-left origin, points) — the same
// space the helper reports.
import CoreGraphics
import Foundation

let args = CommandLine.arguments
guard args.count >= 3, let x = Double(args[1]), let y = Double(args[2]) else {
    FileHandle.standardError.write("usage: synth-click <x> <y> [clicks=1] [downMs=60]\n".data(using: .utf8)!)
    exit(2)
}
let clicks = args.count > 3 ? (Int(args[3]) ?? 1) : 1
let downMs = args.count > 4 ? (useconds_t((Double(args[4]) ?? 60) * 1000)) : 60000

let pt = CGPoint(x: x, y: y)
for i in 0..<clicks {
    let down = CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: pt, mouseButton: .left)
    down?.post(tap: .cghidEventTap)
    usleep(downMs)
    let up = CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: pt, mouseButton: .left)
    up?.post(tap: .cghidEventTap)
    if i + 1 < clicks { usleep(250_000) }
}
FileHandle.standardError.write("posted \(clicks) click(s) at \(x),\(y)\n".data(using: .utf8)!)
