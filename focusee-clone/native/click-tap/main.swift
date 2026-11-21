// Global click listener for macOS — the real-click source for auto zoom.
//
// Design (ticket 0cdd8d5c7d18, plan A): the FocuSee clone previously inferred
// clicks from cursor "dwell" clusters. Real FocuSee zooms on real clicks, so
// the app now runs this tiny helper while recording. It is a separate process
// on purpose: a hang or crash here can never take the recorder down, and the
// accessibility (AX) TCC grant is checked against the responsible process —
// the signed app bundle — not against Electron's generic helper identities.
//
// Protocol (JSON lines on stdout, one line per message, always flushed):
//   {"type":"status","ok":true,"ax":true,"tap":true,"pid":123,"reason":"listening"}
//     -> sent once at startup. ok=false means the event tap could not be
//        created (accessibility not granted); the app must fall back to the
//        dwell heuristic when it sees that.
//   {"type":"event","kind":"leftMouseDown","button":0,"x":640.5,"y":312.25,"ts":1700000000000}
//     -> one line per global mouse DOWN/UP. x/y are in global display
//        coordinates (top-left origin, points) — the same space as Electron's
//        screen.getCursorScreenPoint(), so the renderer can normalize clicks
//        and cursor samples identically. ts is wall-clock ms, matching how
//        the cursor sampler timestamps its samples (Date.now in both).
//
// Usage: focusee-click-tap          listen until SIGTERM/SIGINT
//        focusee-click-tap --probe  create the tap once, report, exit(0|4)
//
// The tap is listen-only (kCGEventTapOptionListenOnly): we can never alter or
// swallow user input. Listen-only taps may still be disabled by the system
// (kCGEventTapDisabledByTimeout / …ByUserInput); we re-enable and keep going.

import CoreGraphics
import Foundation

// Permission preflight (macOS 10.15+): true when listening is already allowed.
// Informational only — the authoritative signal is whether the tap gets created.
let axGranted = CGPreflightListenEventAccess()

let eventMask: CGEventMask =
    (1 << CGEventType.leftMouseDown.rawValue)
    | (1 << CGEventType.leftMouseUp.rawValue)
    | (1 << CGEventType.rightMouseDown.rawValue)
    | (1 << CGEventType.rightMouseUp.rawValue)
    | (1 << CGEventType.otherMouseDown.rawValue)
    | (1 << CGEventType.otherMouseUp.rawValue)

let kindNames: [CGEventType: String] = [
    .leftMouseDown: "leftMouseDown",
    .leftMouseUp: "leftMouseUp",
    .rightMouseDown: "rightMouseDown",
    .rightMouseUp: "rightMouseUp",
    .otherMouseDown: "otherMouseDown",
    .otherMouseUp: "otherMouseUp",
]

var tapRef: CFMachPort?

func emit(_ line: String) {
    FileHandle.standardOutput.write((line + "\n").data(using: .utf8)!)
}

func emitStatus(ok: Bool, reason: String) {
    let status = "{\"type\":\"status\",\"ok\":\(ok ? "true" : "false"),\"ax\":\(axGranted ? "true" : "false"),\"tap\":\(ok ? "true" : "false"),\"pid\":\(ProcessInfo.processInfo.processIdentifier),\"reason\":\"\(reason)\"}"
    emit(status)
}

let tapCallback: CGEventTapCallBack = { _, type, event, _ in
    switch type {
    case .tapDisabledByTimeout, .tapDisabledByUserInput:
        // The system throttled the tap (e.g. the machine slept through it).
        // Re-enable and continue listening; do not spam stdout.
        if let tap = tapRef {
            CGEvent.tapEnable(tap: tap, enable: true)
        }
    default:
        if let kind = kindNames[type] {
            let loc = event.location
            let button = event.getIntegerValueField(.mouseEventButtonNumber)
            let ts = Int64(Date().timeIntervalSince1970 * 1000)
            emit("{\"type\":\"event\",\"kind\":\"\(kind)\",\"button\":\(button),\"x\":\(String(format: "%.2f", loc.x)),\"y\":\(String(format: "%.2f", loc.y)),\"ts\":\(ts)}")
        }
    }
    // Listen-only: the return value is ignored, but the C signature requires it.
    return Unmanaged.passUnretained(event)
}

func createTap() -> CFMachPort? {
    CGEvent.tapCreate(
        tap: .cgSessionEventTap,
        place: .headInsertEventTap,
        options: .listenOnly,
        eventsOfInterest: eventMask,
        callback: tapCallback,
        userInfo: nil
    )
}

func failReason() -> String {
    axGranted
        ? "CGEventTapCreate returned NULL even though the accessibility preflight passed"
        : "CGEventTapCreate returned NULL: accessibility permission not granted"
}

if CommandLine.arguments.contains("--probe") {
    // Preflight for the app's permission badge: no long-lived process.
    if let tap = createTap() {
        CFMachPortInvalidate(tap)
        emitStatus(ok: true, reason: "probe-ok")
        exit(0)
    }
    emitStatus(ok: false, reason: failReason())
    exit(4)
}

guard let tap = createTap() else {
    emitStatus(ok: false, reason: failReason())
    exit(4)
}
tapRef = tap
CGEvent.tapEnable(tap: tap, enable: true)

let source = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
CFRunLoopAddSource(CFRunLoopGetCurrent(), source, .commonModes)

signal(SIGTERM) { _ in exit(0) }
signal(SIGINT) { _ in exit(0) }

emitStatus(ok: true, reason: "listening")
CFRunLoopRun()
// Not reached except via exit signals.
