#!/usr/bin/env python3
"""Generate Executive PowerPoint Presentation for PySURVEILLANCE.

Builds a 16:9 widescreen presentation deck (PySURVEILLANCE_Presentation.pptx)
featuring genuine 1080p application screenshots, decoupled edge architecture,
neural inference, forensic extraction, acoustic intelligence, and security.
"""

import os
import sys
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_ROOT / "presentation" / "assets"
OUTPUT_PPTX = PROJECT_ROOT / "presentation" / "PySURVEILLANCE_Presentation.pptx"
ROOT_PPTX = PROJECT_ROOT / "PySURVEILLANCE_Presentation.pptx"

# -----------------------------------------------------------------------------
# Color Palette (Obsidian / High-Tech Cyber Deck)
# -----------------------------------------------------------------------------
BG_COLOR = RGBColor(11, 15, 25)         # Deep Obsidian #0B0F19
CARD_BG = RGBColor(19, 27, 46)          # Dark Slate Container #131B2E
CARD_BORDER = RGBColor(33, 46, 74)      # Subtle Border #212E4A
TEXT_MAIN = RGBColor(248, 250, 252)     # Off-White #F8FAFC
TEXT_MUTED = RGBColor(148, 163, 184)    # Cool Slate #94A3B8
ACCENT_CYAN = RGBColor(0, 212, 255)     # Electric Cyan #00D4FF
ACCENT_GREEN = RGBColor(16, 185, 129)   # Emerald #10B981
ACCENT_AMBER = RGBColor(245, 158, 11)   # Amber #F59E0B
ACCENT_RED = RGBColor(239, 68, 68)      # Danger Coral #EF4444
ACCENT_PURPLE = RGBColor(168, 85, 247)  # Electric Purple #A855F7

FONT_HEADING = "Segoe UI"
FONT_BODY = "Arial"

TOTAL_SLIDES = 18


class PresentationBuilder:
    def __init__(self):
        self.prs = Presentation()
        # Set 16:9 Widescreen (13.333 x 7.5 inches)
        self.prs.slide_width = Inches(13.333)
        self.prs.slide_height = Inches(7.5)
        self.blank_layout = self.prs.slide_layouts[6]
        self.slide_count = 0

    def add_blank_slide(self):
        slide = self.prs.slides.add_slide(self.blank_layout)
        self.slide_count += 1
        
        # Add background rectangle
        bg = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, 0, 0, self.prs.slide_width, self.prs.slide_height
        )
        bg.fill.solid()
        bg.fill.fore_color.rgb = BG_COLOR
        bg.line.fill.background()
        
        # Add top glow line
        top_line = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, 0, 0, self.prs.slide_width, Inches(0.05)
        )
        top_line.fill.solid()
        top_line.fill.fore_color.rgb = ACCENT_CYAN
        top_line.line.fill.background()

        return slide

    def add_footer(self, slide, current_idx):
        footer_box = slide.shapes.add_textbox(
            Inches(0.8), Inches(7.05), Inches(11.733), Inches(0.35)
        )
        tf = footer_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.text = "PySURVEILLANCE Edge Platform  |  Hardware-Independent Intelligent Security  |  github.com/ss3325713/survelance"
        p.font.name = FONT_BODY
        p.font.size = Pt(9)
        p.font.color.rgb = RGBColor(80, 95, 120)

        # Slide Number
        p_num = tf.add_paragraph()
        p_num.alignment = PP_ALIGN.RIGHT
        p_num.text = f"{current_idx} / {TOTAL_SLIDES}"
        p_num.font.name = FONT_BODY
        p_num.font.size = Pt(9)
        p_num.font.bold = True
        p_num.font.color.rgb = ACCENT_CYAN

    def add_header(self, slide, tag: str, title: str, subtitle: str):
        header_box = slide.shapes.add_textbox(
            Inches(0.8), Inches(0.35), Inches(11.733), Inches(1.1)
        )
        tf = header_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

        # Tag
        if tag:
            p_tag = tf.paragraphs[0]
            p_tag.text = tag.upper()
            p_tag.font.name = FONT_HEADING
            p_tag.font.size = Pt(9.5)
            p_tag.font.bold = True
            p_tag.font.color.rgb = ACCENT_CYAN
            p_tag.space_after = Pt(2)
            p_title = tf.add_paragraph()
        else:
            p_title = tf.paragraphs[0]

        # Title
        p_title.text = title
        p_title.font.name = FONT_HEADING
        p_title.font.size = Pt(21)
        p_title.font.bold = True
        p_title.font.color.rgb = TEXT_MAIN
        p_title.space_after = Pt(3)

        # Subtitle
        p_sub = tf.add_paragraph()
        p_sub.text = subtitle
        p_sub.font.name = FONT_BODY
        p_sub.font.size = Pt(11)
        p_sub.font.color.rgb = TEXT_MUTED

    def add_card(self, slide, left, top, width, height, bg_color=CARD_BG, border_color=CARD_BORDER):
        card = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height
        )
        card.fill.solid()
        card.fill.fore_color.rgb = bg_color
        card.line.color.rgb = border_color
        card.line.width = Pt(1)
        return card

    def add_feature_box(self, slide, left, top, width, height, icon_title: str, body: str, accent_color=ACCENT_CYAN):
        self.add_card(slide, left, top, width, height)

        # Left accent pill strip
        pill = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, left, top + Inches(0.12), Inches(0.04), height - Inches(0.24)
        )
        pill.fill.solid()
        pill.fill.fore_color.rgb = accent_color
        pill.line.fill.background()

        tb = slide.shapes.add_textbox(
            left + Inches(0.2), top + Inches(0.12), width - Inches(0.3), height - Inches(0.24)
        )
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

        p1 = tf.paragraphs[0]
        p1.text = icon_title
        p1.font.name = FONT_HEADING
        p1.font.size = Pt(12)
        p1.font.bold = True
        p1.font.color.rgb = TEXT_MAIN
        p1.space_after = Pt(4)

        p2 = tf.add_paragraph()
        p2.text = body
        p2.font.name = FONT_BODY
        p2.font.size = Pt(9.5)
        p2.font.color.rgb = TEXT_MUTED

    def add_screenshot(self, slide, image_filename: str, left, top, width, height):
        img_path = ASSETS_DIR / image_filename
        if not img_path.exists():
            print(f"[Warning] Image not found: {img_path}")
            return

        # Container frame
        frame = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            left - Inches(0.04),
            top - Inches(0.04),
            width + Inches(0.08),
            height + Inches(0.08)
        )
        frame.fill.solid()
        frame.fill.fore_color.rgb = RGBColor(20, 28, 48)
        frame.line.color.rgb = RGBColor(45, 60, 95)
        frame.line.width = Pt(1.5)

        # Add image
        slide.shapes.add_picture(str(img_path), left, top, width, height)

    def create_title_slide(self):
        slide = self.add_blank_slide()

        # Large center-left decorative banner
        self.add_card(slide, Inches(0.8), Inches(1.0), Inches(11.733), Inches(5.6), CARD_BG, CARD_BORDER)

        # Accent cyan line inside banner
        cyan_strip = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.0), Inches(0.08), Inches(5.6)
        )
        cyan_strip.fill.solid()
        cyan_strip.fill.fore_color.rgb = ACCENT_CYAN
        cyan_strip.line.fill.background()

        tb = slide.shapes.add_textbox(Inches(1.2), Inches(1.4), Inches(11.0), Inches(2.2))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

        p0 = tf.paragraphs[0]
        p0.text = "EDGE-FIRST SECURITY ARCHITECTURE // TECHNICAL OVERVIEW"
        p0.font.name = FONT_HEADING
        p0.font.size = Pt(11)
        p0.font.bold = True
        p0.font.color.rgb = ACCENT_CYAN
        p0.space_after = Pt(8)

        p1 = tf.add_paragraph()
        p1.text = "PySURVEILLANCE"
        p1.font.name = FONT_HEADING
        p1.font.size = Pt(36)
        p1.font.bold = True
        p1.font.color.rgb = TEXT_MAIN
        p1.space_after = Pt(8)

        p2 = tf.add_paragraph()
        p2.text = "Intelligent Edge Surveillance, Perimeter Defense & Threat Deterrence Console"
        p2.font.name = FONT_BODY
        p2.font.size = Pt(15)
        p2.font.color.rgb = TEXT_MUTED

        # 4 Core Highlight Badges
        highlights = [
            ("⚡ Decoupled Edge Runtime", "Autonomous Linux runtime (x86_64 / ARM64) with zero cloud reliance or monthly fees.", ACCENT_CYAN),
            ("🧠 YOLOv8n ONNX Engine", "Event-triggered 1.5 FPS neural classification via OpenCV DNN C++ runtime.", ACCENT_GREEN),
            ("📹 Motion-Triggered Video", "Instant frame-1 recording with 15s inactivity reset and 60s segment rotation.", ACCENT_AMBER),
            ("🔒 Zero-Trust Cryptography", "Salted PBKDF2-HMAC-SHA256 authentication, brute-force lockout, and RFC 1918 firewall.", ACCENT_PURPLE),
        ]

        card_w = Inches(2.65)
        card_h = Inches(1.8)
        start_x = Inches(1.2)
        y_pos = Inches(4.3)
        spacing = Inches(0.24)

        for i, (title, desc, color) in enumerate(highlights):
            x = start_x + i * (card_w + spacing)
            self.add_feature_box(slide, x, y_pos, card_w, card_h, title, desc, color)

        self.add_footer(slide, 1)

    def create_comparison_slide(self):
        slide = self.add_blank_slide()
        self.add_header(
            slide,
            "00 // EXECUTIVE SUMMARY",
            "Traditional Surveillance vs. PySURVEILLANCE",
            "Eliminating cloud subscription lock-in, latency bottlenecks, and invasive facial profiling."
        )

        col_w = Inches(5.7)
        col_h = Inches(5.1)
        top = Inches(1.7)

        # Legacy Card (Left)
        self.add_card(slide, Inches(0.8), top, col_w, col_h, RGBColor(24, 20, 28), RGBColor(70, 30, 40))
        # Left red strip
        strip1 = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), top, Inches(0.06), col_h)
        strip1.fill.solid()
        strip1.fill.fore_color.rgb = ACCENT_RED
        strip1.line.fill.background()

        tb1 = slide.shapes.add_textbox(Inches(1.1), top + Inches(0.3), col_w - Inches(0.5), col_h - Inches(0.6))
        tf1 = tb1.text_frame
        tf1.word_wrap = True
        tf1.margin_left = tf1.margin_top = tf1.margin_right = tf1.margin_bottom = 0

        p1_title = tf1.paragraphs[0]
        p1_title.text = "❌ Legacy CCTV & Cloud Cameras"
        p1_title.font.name = FONT_HEADING
        p1_title.font.size = Pt(16)
        p1_title.font.bold = True
        p1_title.font.color.rgb = ACCENT_RED
        p1_title.space_after = Pt(14)

        flaws = [
            ("High Bandwidth Drain:", "Uploads continuous uncompressed video to cloud data centers 24/7."),
            ("Expensive Recurring Fees:", "Requires ongoing subscriptions for storage, playback, and AI detections."),
            ("Critical Latency Delays:", "Cloud roundtrips delay intrusion alerts by 5 to 30 seconds."),
            ("Invasive Facial Profiling:", "Feeds raw facial biometric data into proprietary training models."),
            ("Single Point of Failure:", "An internet outage disables alerts, recording, and camera monitoring.")
        ]
        for bold, text in flaws:
            p = tf1.add_paragraph()
            p.space_after = Pt(10)
            run_b = p.add_run()
            run_b.text = f"• {bold} "
            run_b.font.name = FONT_BODY
            run_b.font.size = Pt(10.5)
            run_b.font.bold = True
            run_b.font.color.rgb = RGBColor(255, 170, 170)
            run_t = p.add_run()
            run_t.text = text
            run_t.font.name = FONT_BODY
            run_t.font.size = Pt(10)
            run_t.font.color.rgb = TEXT_MUTED

        # PySURVEILLANCE Card (Right)
        self.add_card(slide, Inches(6.8), top, col_w, col_h, RGBColor(16, 28, 35), RGBColor(25, 65, 55))
        strip2 = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(6.8), top, Inches(0.06), col_h)
        strip2.fill.solid()
        strip2.fill.fore_color.rgb = ACCENT_GREEN
        strip2.line.fill.background()

        tb2 = slide.shapes.add_textbox(Inches(7.1), top + Inches(0.3), col_w - Inches(0.5), col_h - Inches(0.6))
        tf2 = tb2.text_frame
        tf2.word_wrap = True
        tf2.margin_left = tf2.margin_top = tf2.margin_right = tf2.margin_bottom = 0

        p2_title = tf2.paragraphs[0]
        p2_title.text = "✅ PySURVEILLANCE Edge Platform"
        p2_title.font.name = FONT_HEADING
        p2_title.font.size = Pt(16)
        p2_title.font.bold = True
        p2_title.font.color.rgb = ACCENT_GREEN
        p2_title.space_after = Pt(14)

        benefits = [
            ("Zero Cloud Dependence:", "100% of processing, inference, and storage executes locally on host."),
            ("Open Standards Architecture:", "Supports standard RTSP, HTTP/MJPEG, and Linear PCM WAV streams."),
            ("Sub-50ms Edge Response:", "Immediate local threat classification and instant laptop speaker sirens."),
            ("Strict Ethical Architecture:", "Zero biometric facial recognition; automatic privacy face blurring."),
            ("Air-Gapped Resiliency:", "Fully functional without internet connection; isolated inside private LAN.")
        ]
        for bold, text in benefits:
            p = tf2.add_paragraph()
            p.space_after = Pt(10)
            run_b = p.add_run()
            run_b.text = f"• {bold} "
            run_b.font.name = FONT_BODY
            run_b.font.size = Pt(10.5)
            run_b.font.bold = True
            run_b.font.color.rgb = RGBColor(180, 255, 220)
            run_t = p.add_run()
            run_t.text = text
            run_t.font.name = FONT_BODY
            run_t.font.size = Pt(10)
            run_t.font.color.rgb = TEXT_MUTED

        self.add_footer(slide, 2)

    def create_architecture_slide(self):
        slide = self.add_blank_slide()
        self.add_header(
            slide,
            "SYSTEM ARCHITECTURE",
            "Decoupled Multithreaded Pipeline Architecture",
            "Zero dropped frames: Stream ingestion, neural inference, and video encoding operate in isolated queues."
        )

        tiers = [
            ("1. Decoupled Ingestion & Hardware Telemetry", [
                ("RTSP / H.264 / H.265:", "Network CCTV feeds via OpenCV VideoCapture."),
                ("HTTP / MJPEG Feed:", "High-framerate video stream (/video)."),
                ("HTTP Linear PCM Audio:", "Dedicated audio stream (/audio.wav)."),
                ("Device Sensors Telemetry:", "Battery, temperature, and AC status (/sensors.json).")
            ], ACCENT_CYAN),
            ("2. Real-Time Core Engines (FastAPI Runtime)", [
                ("CameraWorker:", "Bounded frame queue preventing memory buildup."),
                ("OpenCV MOG2 Subtractor:", "Instant pixel-level background motion evaluation."),
                ("FlashlightController:", "Illumination automation in low-light environments."),
                ("AudioDetector:", "Adaptive noise floor and RMS energy spike analysis.")
            ], ACCENT_GREEN),
            ("3. Asynchronous Storage & Forensics Queue", [
                ("VideoRecorder:", "60s segment rotation with 15s inactivity reset."),
                ("SQLite video_jobs Queue:", "Crash-resilient persistent background queue."),
                ("Laplacian Variance Filter:", "Discards blurred frames to extract sharp keyframes."),
                ("YOLOv8n ONNX Engine:", "CPU-optimized neural classification via OpenCV DNN.")
            ], ACCENT_AMBER)
        ]

        card_w = Inches(3.75)
        card_h = Inches(4.9)
        top = Inches(1.8)
        start_x = Inches(0.8)
        spacing = Inches(0.24)

        for i, (title, items, color) in enumerate(tiers):
            x = start_x + i * (card_w + spacing)
            self.add_card(slide, x, top, card_w, card_h)

            pill = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, top, card_w, Inches(0.06))
            pill.fill.solid()
            pill.fill.fore_color.rgb = color
            pill.line.fill.background()

            tb = slide.shapes.add_textbox(x + Inches(0.25), top + Inches(0.3), card_w - Inches(0.5), card_h - Inches(0.5))
            tf = tb.text_frame
            tf.word_wrap = True
            tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

            p_head = tf.paragraphs[0]
            p_head.text = title
            p_head.font.name = FONT_HEADING
            p_head.font.size = Pt(13)
            p_head.font.bold = True
            p_head.font.color.rgb = color
            p_head.space_after = Pt(16)

            for label, desc in items:
                p = tf.add_paragraph()
                p.space_after = Pt(12)
                r1 = p.add_run()
                r1.text = f"{label}\n"
                r1.font.name = FONT_BODY
                r1.font.size = Pt(10.5)
                r1.font.bold = True
                r1.font.color.rgb = TEXT_MAIN

                r2 = p.add_run()
                r2.text = desc
                r2.font.name = FONT_BODY
                r2.font.size = Pt(9.5)
                r2.font.color.rgb = TEXT_MUTED

        self.add_footer(slide, 3)

    def create_screenshot_slide(
        self,
        slide_num: int,
        tag: str,
        title: str,
        subtitle: str,
        screenshot_file: str,
        features: list
    ):
        slide = self.add_blank_slide()
        self.add_header(slide, tag, title, subtitle)

        # Left Column: High-Res Screenshot (7.3 inches wide, 4.106 inches high, 16:9 ratio)
        img_left = Inches(0.8)
        img_top = Inches(1.8)
        img_width = Inches(7.5)
        img_height = Inches(4.22)
        self.add_screenshot(slide, screenshot_file, img_left, img_top, img_width, img_height)

        # Right Column: 3 Feature Cards
        right_left = Inches(8.55)
        right_width = Inches(3.98)
        card_height = Inches(1.3)
        card_spacing = Inches(0.16)

        accents = [ACCENT_CYAN, ACCENT_GREEN, ACCENT_AMBER]

        for i, (card_title, card_body) in enumerate(features):
            top_pos = img_top + i * (card_height + card_spacing)
            color = accents[i % len(accents)]
            self.add_feature_box(slide, right_left, top_pos, right_width, card_height, card_title, card_body, color)

        self.add_footer(slide, slide_num)

    def create_ethics_slide(self):
        slide = self.add_blank_slide()
        self.add_header(
            slide,
            "ETHICAL SURVEILLANCE & CIVIL LIBERTIES",
            "Ethical Surveillance & Human Rights Architecture",
            "Uncompromising perimeter security while strictly upholding privacy, civil liberties, and human dignity."
        )

        pillars = [
            ("🚫 Zero Facial Recognition",
             "Biometric face profiling, facial embeddings, and identity databases are strictly excluded from the codebase. Detections report strictly as generic 'Person' entities.",
             ACCENT_RED),
            ("🎭 Privacy Face Blurring",
             "All human faces featured in public documentation, marketing screenshots, and presentation slide decks are systematically obscured with Gaussian blur (ksize=51x51).",
             ACCENT_CYAN),
            ("🐾 Species Verification Caution",
             "Standard COCO models cannot verify specialized wildlife or primates. Detections outside benchmark certainty report strictly as 'Animal detected — species unconfirmed'.",
             ACCENT_AMBER),
            ("🔇 In-Memory Audio Analysis",
             "Network audio is processed strictly in volatile memory for acoustic RMS energy spikes and SNR alarms. Continuous ambient voice audio is never stored or written to disk.",
             ACCENT_GREEN),
        ]

        card_w = Inches(5.7)
        card_h = Inches(2.25)
        start_x = Inches(0.8)
        start_y = Inches(1.8)
        spacing_x = Inches(0.33)
        spacing_y = Inches(0.24)

        for i, (title, desc, color) in enumerate(pillars):
            col = i % 2
            row = i // 2
            x = start_x + col * (card_w + spacing_x)
            y = start_y + row * (card_h + spacing_y)
            self.add_feature_box(slide, x, y, card_w, card_h, title, desc, color)

        self.add_footer(slide, 17)

    def create_conclusion_slide(self):
        slide = self.add_blank_slide()
        self.add_header(
            slide,
            "PRODUCTION READINESS",
            "Platform Summary & Technical Specifications",
            "A battle-tested, autonomous edge surveillance system ready for production deployment."
        )

        specs = [
            ("⚡ High Performance", [
                "Sub-50ms live stream rendering with hardware acceleration",
                "1.5 FPS CPU-friendly YOLOv8n ONNX inference",
                "Non-blocking background video processing queue"
            ], ACCENT_CYAN),
            ("📦 Storage & Forensics", [
                "15s inactivity reset with 60s max segment rotation",
                "Laplacian variance sharpness scoring for clean keyframes",
                "Automated rolling disk quota management"
            ], ACCENT_GREEN),
            ("🔌 Universal Compatibility", [
                "Native RTSP (H.264 / H.265) and HTTP/MJPEG video",
                "Independent HTTP Linear PCM audio streaming",
                "Support for smartphones, ONVIF, and IP cameras"
            ], ACCENT_AMBER),
            ("🛡️ Zero-Trust Security", [
                "Salted PBKDF2-HMAC-SHA256 (100,000 rounds)",
                "5-strike brute-force rate limiter (300s lockout)",
                "RFC 1918 private LAN isolation firewall"
            ], ACCENT_PURPLE),
        ]

        card_w = Inches(2.75)
        card_h = Inches(3.4)
        top = Inches(1.8)
        start_x = Inches(0.8)
        spacing = Inches(0.24)

        for i, (title, items, color) in enumerate(specs):
            x = start_x + i * (card_w + spacing)
            self.add_card(slide, x, top, card_w, card_h)

            pill = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, top, card_w, Inches(0.06))
            pill.fill.solid()
            pill.fill.fore_color.rgb = color
            pill.line.fill.background()

            tb = slide.shapes.add_textbox(x + Inches(0.2), top + Inches(0.25), card_w - Inches(0.4), card_h - Inches(0.4))
            tf = tb.text_frame
            tf.word_wrap = True
            tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

            p_head = tf.paragraphs[0]
            p_head.text = title
            p_head.font.name = FONT_HEADING
            p_head.font.size = Pt(13)
            p_head.font.bold = True
            p_head.font.color.rgb = color
            p_head.space_after = Pt(14)

            for bullet in items:
                p = tf.add_paragraph()
                p.space_after = Pt(10)
                p.text = f"• {bullet}"
                p.font.name = FONT_BODY
                p.font.size = Pt(9.5)
                p.font.color.rgb = TEXT_MUTED

        # Bottom Callout Card
        bottom_top = Inches(5.45)
        bottom_h = Inches(1.25)
        self.add_card(slide, Inches(0.8), bottom_top, Inches(11.733), bottom_h, RGBColor(16, 24, 38), RGBColor(30, 48, 75))
        
        strip = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), bottom_top, Inches(0.06), bottom_h)
        strip.fill.solid()
        strip.fill.fore_color.rgb = ACCENT_CYAN
        strip.line.fill.background()

        tb_bot = slide.shapes.add_textbox(Inches(1.1), bottom_top + Inches(0.2), Inches(11.2), bottom_h - Inches(0.4))
        tf_bot = tb_bot.text_frame
        tf_bot.word_wrap = True
        tf_bot.margin_left = tf_bot.margin_top = tf_bot.margin_right = tf_bot.margin_bottom = 0

        pb1 = tf_bot.paragraphs[0]
        pb1.text = "🚀 GitHub Repository & Technical Documentation"
        pb1.font.name = FONT_HEADING
        pb1.font.size = Pt(12)
        pb1.font.bold = True
        pb1.font.color.rgb = TEXT_MAIN
        pb1.space_after = Pt(4)

        pb2 = tf_bot.add_paragraph()
        pb2.text = "Repository: https://github.com/ss3325713/survelance   |   Branch: main   |   Commit: db1efb2   |   Environment: Linux Mint / Ubuntu"
        pb2.font.name = FONT_BODY
        pb2.font.size = Pt(10)
        pb2.font.color.rgb = ACCENT_CYAN

        self.add_footer(slide, 18)

    def build_full_deck(self):
        print("[DeckBuilder] Generating Title Slide...")
        self.create_title_slide()

        print("[DeckBuilder] Generating Executive Comparison Slide...")
        self.create_comparison_slide()

        print("[DeckBuilder] Generating Architecture Slide...")
        self.create_architecture_slide()

        # Slide 4: Main Dashboard
        print("[DeckBuilder] Generating Slide 4: Main Monitoring Dashboard...")
        self.create_screenshot_slide(
            4,
            "01 // COMMAND CONSOLE",
            "Real-Time Security Operations Center (SOC) Command Console",
            "Centralized situational awareness: live stream preview, hardware health, and daily incident metrics.",
            "01_Main_Monitoring_Dashboard.png",
            [
                ("⚡ Sub-50ms MJPEG Streaming", "Ultra-low-latency video preview with continuous resolution and acquisition FPS telemetry."),
                ("🔋 Device Hardware Telemetry", "Real-time battery percentage, thermal monitoring, and AC/PoE power status."),
                ("📊 Real-Time Threat Metrics", "Dynamic perimeter event counters, severity summaries, and multi-frame alert cards.")
            ]
        )

        # Slide 5: Live Cinema Monitoring
        print("[DeckBuilder] Generating Slide 5: Live Cinema Monitoring...")
        self.create_screenshot_slide(
            5,
            "02 // CINEMA WORKSPACE",
            "Full-Framerate Cinema Workspace & Floating HUD",
            "Dedicated perimeter observation with non-intrusive target alert overlays and software tone mapping.",
            "02_Live_Cinema_Monitoring.png",
            [
                ("🚨 Floating Target Alerts", "Instant visual notifications (🚨 PERSON 83% DETECTED) overlaid without obstructing controls."),
                ("📹 Recording Status HUD", "Live recording indicator badge tracking active elapsed duration and segment index."),
                ("🎛️ Software Tone Mapping", "Real-time gamma (0.5–2.0), brightness, contrast, and backlight HDR compensation.")
            ]
        )

        # Slide 6: Neural Classification
        print("[DeckBuilder] Generating Slide 6: Neural Classification...")
        self.create_screenshot_slide(
            6,
            "03 // NEURAL CLASSIFIER",
            "YOLOv8n ONNX Deep Learning & OpenCV MOG2 Subtraction",
            "Dual-engine architecture combining rapid background subtraction with deep convolutional neural inference.",
            "03_Detection_Classification_Center.png",
            [
                ("🎯 Spatial Overlap Verification", "Neural detections strictly correlated with active visual motion bounding boxes to suppress false positives."),
                ("🎚️ Runtime Sensitivity Sliders", "Instant adjustment of MOG2 VarThreshold and neural confidence cutoff with zero service restarts."),
                ("⚡ CPU-Optimized Inference", "OpenCV DNN C++ backend executing 1.5 FPS event-driven inference on standard CPUs.")
            ]
        )

        # Slide 7: Motion Recording
        print("[DeckBuilder] Generating Slide 7: Motion-Triggered Recording...")
        self.create_screenshot_slide(
            7,
            "04 // VIDEO RECORDING",
            "Motion-Triggered Video Recording & Segment Rollover",
            "Continuous incident capture without unbounded file growth or memory leaks.",
            "04_Recording_Status_HUD.png",
            [
                ("⏱️ Immediate Motion Trigger", "Video recording initiates on frame 1 of qualifying visual motion without waiting for neural inference."),
                ("🔄 15-Second Inactivity Timer", "Countdown resets on every recurring motion event. Continues same recording if subject moves again."),
                ("📦 60-Second Segment Rotation", "Continuous events automatically split into clean 60-second video segments under the same incident session.")
            ]
        )

        # Slide 8: Incident History
        print("[DeckBuilder] Generating Slide 8: Event Timeline Records...")
        self.create_screenshot_slide(
            8,
            "05 // INCIDENT AUDIT",
            "Chronological Incident History & Multi-Frame Progression",
            "Audited record of perimeter events with automated three-stage keyframe capture.",
            "05_Event_Timeline_Records.png",
            [
                ("📸 Three-Stage Keyframe Capture", "Automatically preserves Initial Trigger, Peak Motion Change, and Final Concluding frames for every incident."),
                ("🔍 Dynamic Category Filtering", "Fast filtering across Person, Animal, Bird, and Unknown Object classes with severity classification."),
                ("📈 Acoustic & Lux Correlation", "Logs synchronized microphone RMS energy and ambient lux levels at the exact moment of breach.")
            ]
        )

        # Slide 9: Incident Gallery
        print("[DeckBuilder] Generating Slide 9: Incident Gallery Grid...")
        self.create_screenshot_slide(
            9,
            "06 // INCIDENT GALLERY",
            "Visual Card Grid for Rapid Threat Screening",
            "High-density card grid optimized for swift threat pattern recognition and evidence export.",
            "06_Incident_Gallery_Grid.png",
            [
                ("🖼️ High-Density Card Grid", "Thumbnail cards with category badges, confidence ratings, and ISO-8601 timestamps."),
                ("💾 One-Click Cryptographic Export", "Direct download of full-resolution forensic JPEGs with embedded metadata."),
                ("🔎 One-Click Forensic Inspection", "Instant modal launch for multi-frame inspection and sharpness comparison.")
            ]
        )

        # Slide 10: Forensic Extraction
        print("[DeckBuilder] Generating Slide 10: Extracted Forensic Images...")
        self.create_screenshot_slide(
            10,
            "07 // FORENSIC EXTRACTION",
            "Laplacian Variance Sharpness Scoring & Deep Forensics",
            "Background worker extracts the sharpest forensic keyframes from recorded video segments.",
            "07_Extracted_Forensic_Images.png",
            [
                ("📐 Laplacian Variance Formula", "Evaluates frame focus score to systematically discard motion-blurred frames."),
                ("🗄️ Persistent SQLite Job Queue", "Closed video segments queued in video_jobs table, surviving reboots without job loss."),
                ("🔬 Side-by-Side Comparison", "Modal displays trigger snapshot, peak frame, concluding frame, and extracted video keyframe.")
            ]
        )

        # Slide 11: Acoustic Intelligence
        print("[DeckBuilder] Generating Slide 11: Acoustic Intelligence...")
        self.create_screenshot_slide(
            11,
            "08 // ACOUSTIC INTELLIGENCE",
            "Phone Microphone RMS Energy & Noise Floor Monitoring",
            "Network audio stream analysis with dynamic ambient noise floor tracking.",
            "08_Acoustic_Intelligence_Audio.png",
            [
                ("📈 Dynamic Rolling Noise Floor", "Adaptive alpha filter continuously learns ambient acoustics to suppress false sound triggers."),
                ("📶 Signal-to-Noise Ratio (SNR)", "Sound alerts trigger only when audio energy spikes exceed the ambient noise floor."),
                ("🔒 Network Stream Isolation", "Ingests audio via HTTP linear PCM (/audio.wav), bypassing local laptop microphones.")
            ]
        )

        # Slide 12: Hardware Lighting
        print("[DeckBuilder] Generating Slide 12: Hardware Automation...")
        self.create_screenshot_slide(
            12,
            "09 // HARDWARE AUTOMATION",
            "Ambient Darkness Detection & Motion-Triggered Flashlight",
            "Smart illumination automation activates lighting only when motion occurs in the dark.",
            "09_Hardware_Automation_Lighting.png",
            [
                ("🌙 Lux-Aware Illumination", "Scene brightness evaluated in real-time (lux_threshold: 45.0); daytime motion never triggers lighting."),
                ("⏳ 15-Second Inactivity Countdown", "Light remains active while motion continues and cleanly turns off 15 seconds after motion ceases."),
                ("💡 Force Overrides & Torch API", "Manual FORCE ON, FORCE OFF, and AUTO modes with seamless IP Webcam torch integration.")
            ]
        )

        # Slide 13: Notifications & Deterrence
        print("[DeckBuilder] Generating Slide 13: Notification Interface...")
        self.create_screenshot_slide(
            13,
            "10 // NOTIFICATIONS & DETERRENCE",
            "Native Device Push Notifications & Host Speaker Sirens",
            "Dual-channel notification: immediate desktop/mobile alerts and audible deterrence.",
            "10_Notification_Interface.png",
            [
                ("📲 Browser & Device Push Alerts", "Service Worker push alerts deliver threat notifications with snapshot thumbnails directly to operator devices."),
                ("🔊 Local Speaker Deterrent Siren", "Synthesizes deterrent tones via host paplay / aplay upon verified Person or Animal intrusions."),
                ("⏱️ Per-Class Alarm Cooldowns", "Configurable cooldown timers (30s Person, 20s Animal) prevent alarm fatigue.")
            ]
        )

        # Slide 14: System Diagnostics
        print("[DeckBuilder] Generating Slide 14: System Diagnostics...")
        self.create_screenshot_slide(
            14,
            "11 // SYSTEM TELEMETRY",
            "Resource-Conscious Performance & System Telemetry",
            "Engineered for continuous 24/7 reliability on standard laptops, mini-PCs, and edge nodes.",
            "11_System_Diagnostics_Telemetry.png",
            [
                ("⚡ Dual-Rate FPS Monitoring", "Tracks camera ingestion (10-15 FPS) vs. neural inference rate (1.5 FPS) for smooth operation."),
                ("💻 CPU & RAM Monitoring", "Real-time system graphs with automatic CPU throttling safeguards when host CPU exceeds 85%."),
                ("🧹 Rolling Storage Retention", "Background storage manager cleans oldest recordings when disk usage reaches quota (2048 MB).")
            ]
        )

        # Slide 15: Stream Configuration
        print("[DeckBuilder] Generating Slide 15: Camera & Audio Stream Configuration...")
        self.create_screenshot_slide(
            15,
            "12 // STREAM CONFIGURATION",
            "Decoupled Protocols & Hardware Independence",
            "Universal compatibility with RTSP IP cameras, smartphone cameras, and HTTP streams.",
            "12_Camera_Audio_Configuration.png",
            [
                ("📹 Standard Video Protocols", "Direct ingestion of RTSP (H.264 / H.265) feeds or multipart HTTP/MJPEG streams via OpenCV VideoCapture."),
                ("🎙️ Independent Audio Channel", "Audio streams independently over uncompressed Linear PCM WAV (/audio.wav) over HTTP."),
                ("⚙️ Hardware Profile Adapters", "Adaptable profiles (auto, ip_webcam, generic) ensure smooth operation across smartphones and commercial IP cameras.")
            ]
        )

        # Slide 16: Security & Access Control
        print("[DeckBuilder] Generating Slide 16: Security Firewall & Access Control...")
        self.create_screenshot_slide(
            16,
            "13 // ZERO-TRUST SECURITY",
            "Cryptographic Security & RFC 1918 Private Firewall",
            "Zero default backdoors, salted PBKDF2 authentication, and strict private LAN isolation.",
            "13_Security_Access_Control.png",
            [
                ("🔑 Salted PBKDF2-HMAC-SHA256", "Master PIN is hashed with 100,000 iterations and 16-byte cryptographic salt; plaintext credentials never touch disk."),
                ("🛑 Brute-Force Rate Limiting", "5 consecutive failed authentication attempts trigger an automatic 300-second IP lockout (HTTP 429)."),
                ("🛡️ RFC 1918 Private Firewall", "Rejects all public internet requests by default (HTTP 403), restricting access strictly to private subnets and localhost.")
            ]
        )

        # Slide 17: Ethical Surveillance
        print("[DeckBuilder] Generating Slide 17: Ethical Surveillance...")
        self.create_ethics_slide()

        # Slide 18: Summary & Conclusions
        print("[DeckBuilder] Generating Slide 18: Platform Summary...")
        self.create_conclusion_slide()

        # Save presentations
        OUTPUT_PPTX.parent.mkdir(parents=True, exist_ok=True)
        self.prs.save(str(OUTPUT_PPTX))
        print(f"[✓] Saved presentation to: {OUTPUT_PPTX}")

        # Also copy to workspace root
        import shutil
        shutil.copyfile(str(OUTPUT_PPTX), str(ROOT_PPTX))
        print(f"[✓] Copied presentation to workspace root: {ROOT_PPTX}")


if __name__ == "__main__":
    builder = PresentationBuilder()
    builder.build_full_deck()
