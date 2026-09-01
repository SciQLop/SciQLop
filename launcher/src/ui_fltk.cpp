#include "ui_fltk.hpp"

#include <FL/Fl.H>
#include <FL/Fl_Box.H>
#include <FL/Fl_Button.H>
#include <FL/Fl_PNG_Image.H>
#include <FL/Fl_Text_Buffer.H>
#include <FL/Fl_Text_Display.H>
#include <FL/Fl_Window.H>
#include <FL/fl_draw.H>

#include <algorithm>
#include <thread>
#include <utility>

namespace sciqlop {
namespace {

constexpr int WIDTH = 720;
constexpr int IMAGE_H = 434;
constexpr int STRIP_H = 84;
constexpr int BANNER_H = 62;
constexpr int BUTTON_ROW_H = 50;
constexpr int PAD = 20;

// Sampled from the splash artwork so the chrome belongs to the same picture.
constexpr uchar BRAND[3] = {112, 45, 137};
constexpr uchar ACCENT[3] = {91, 140, 230};

Fl_Color rgb(const uchar (&c)[3]) { return fl_rgb_color(c[0], c[1], c[2]); }
Fl_Color rgb(uchar r, uchar g, uchar b) { return fl_rgb_color(r, g, b); }

Fl_Color lerp(Fl_Color a, Fl_Color b, double t) {
    uchar ar, ag, ab, br, bg, bb;
    Fl::get_color(a, ar, ag, ab);
    Fl::get_color(b, br, bg, bb);
    return fl_rgb_color(static_cast<uchar>(ar + (br - ar) * t),
                        static_cast<uchar>(ag + (bg - ag) * t),
                        static_cast<uchar>(ab + (bb - ab) * t));
}

void vertical_gradient(int x, int y, int w, int h, Fl_Color top, Fl_Color bottom) {
    for (int i = 0; i < h; ++i) {
        fl_color(lerp(top, bottom, static_cast<double>(i) / std::max(1, h - 1)));
        fl_xyline(x, y + i, x + w - 1);
    }
}

/// Rounded rect as a centre slab plus four quarter-pies. Radii stay small
/// (<= 6 px) because FLTK's X11 driver does not antialias shape edges.
void rounded_rectf(int x, int y, int w, int h, int r, Fl_Color c) {
    fl_color(c);
    r = std::min(r, std::min(w, h) / 2);
    if (r <= 0) {
        fl_rectf(x, y, w, h);
        return;
    }
    fl_rectf(x + r, y, w - 2 * r, h);
    fl_rectf(x, y + r, r, h - 2 * r);
    fl_rectf(x + w - r, y + r, r, h - 2 * r);
    const int d = 2 * r;
    fl_pie(x, y, d, d, 90, 180);
    fl_pie(x + w - d, y, d, d, 0, 90);
    fl_pie(x, y + h - d, d, d, 180, 270);
    fl_pie(x + w - d, y + h - d, d, d, 270, 360);
}

class CaptionStrip : public Fl_Widget {
public:
    CaptionStrip(int x, int y, int w, int h) : Fl_Widget(x, y, w, h) {}

    void phase(std::string t) { phase_ = std::move(t); redraw(); }
    void detail(std::string t) { detail_ = std::move(t); redraw(); }
    void progress(double percent) { progress_ = std::clamp(percent, 0.0, 100.0); redraw(); }

    void draw() override {
        vertical_gradient(x(), y(), w(), h(), rgb(24, 27, 35), rgb(13, 15, 20));
        fl_color(rgb(BRAND));
        fl_xyline(x(), y(), x() + w() - 1);

        fl_color(rgb(255, 255, 255));
        fl_font(FL_HELVETICA_BOLD, 15);
        fl_draw(phase_.c_str(), x() + PAD, y() + 16, w() - 2 * PAD, 18,
                FL_ALIGN_LEFT | FL_ALIGN_INSIDE);

        fl_color(rgb(150, 160, 178));
        fl_font(FL_HELVETICA, 11);
        fl_draw(detail_.c_str(), x() + PAD, y() + 36, w() - 2 * PAD, 14,
                FL_ALIGN_LEFT | FL_ALIGN_INSIDE);

        draw_progress(x() + PAD, y() + h() - 22, w() - 2 * PAD, 6);
    }

private:
    void draw_progress(int px, int py, int pw, int ph) const {
        rounded_rectf(px, py, pw, ph, ph / 2, rgb(38, 42, 54));
        const int filled = static_cast<int>(pw * progress_ / 100.0);
        if (filled < ph) return;
        for (int i = 0; i < filled; ++i) {
            const double t = static_cast<double>(i) / std::max(1, filled - 1);
            fl_color(lerp(rgb(BRAND), rgb(ACCENT), t));
            fl_yxline(px + i, py, py + ph - 1);
        }
        rounded_rectf(px, py, ph, ph, ph / 2, rgb(BRAND));
    }

    std::string phase_;
    std::string detail_;
    double progress_ = 0.0;
};

class FlatButton : public Fl_Button {
public:
    FlatButton(int x, int y, int w, int h, const char* label, bool primary = false)
        : Fl_Button(x, y, w, h, label), primary_(primary) {
        box(FL_NO_BOX);
        labelfont(FL_HELVETICA_BOLD);
        labelsize(12);
    }

    void draw() override {
        Fl_Color base = primary_ ? rgb(BRAND) : rgb(42, 47, 58);
        if (hover_) base = lerp(base, rgb(255, 255, 255), 0.14);
        rounded_rectf(x(), y(), w(), h(), 5, base);
        fl_color(rgb(238, 240, 245));
        fl_font(labelfont(), labelsize());
        fl_draw(label(), x(), y(), w(), h(), FL_ALIGN_CENTER);
    }

    int handle(int event) override {
        if (event == FL_ENTER) { hover_ = true; redraw(); return 1; }
        if (event == FL_LEAVE) { hover_ = false; redraw(); return 1; }
        return Fl_Button::handle(event);
    }

private:
    bool primary_;
    bool hover_ = false;
};

class WarningBanner : public Fl_Widget {
public:
    WarningBanner(int x, int y, int w, int h) : Fl_Widget(x, y, w, h) {}

    void message(std::string m) { message_ = std::move(m); redraw(); }

    void draw() override {
        fl_rectf(x(), y(), w(), h(), rgb(232, 172, 30));
        fl_color(rgb(120, 84, 0));
        fl_xyline(x(), y(), x() + w() - 1);
        fl_color(rgb(38, 28, 0));
        fl_font(FL_HELVETICA_BOLD, 12);
        fl_draw(message_.c_str(), x() + PAD, y() + 10, w() - 2 * PAD, h() - 20,
                FL_ALIGN_LEFT | FL_ALIGN_TOP | FL_ALIGN_WRAP);
    }

private:
    std::string message_;
};

/// Messages posted from the worker thread and applied on the UI thread.
enum class PostKind { Phase, Detail, Progress, Warning, Error, Close };

struct Post {
    PostKind kind;
    std::string text;
    double value = 0.0;
    class FltkUi* ui = nullptr;
};

class FltkUi : public Ui {
public:
    explicit FltkUi(const std::filesystem::path& splash_png) {
        Fl::lock();  // enables Fl::awake() delivery from worker threads
        Fl::set_font(FL_HELVETICA, "Open Sans");
        Fl::set_font(FL_HELVETICA_BOLD, "Open Sans Semibold");
        Fl::set_font(FL_COURIER, "Noto Sans Mono");
        build(splash_png);
    }

    ~FltkUi() override { delete window_; }

    void set_phase(const std::string& text) { strip_->phase(text); }
    void set_detail(const std::string& text) { strip_->detail(text); }
    void set_progress(double percent) { strip_->progress(percent); }

    void show_warning(const std::string& message) {
        banner_->message(message);
        banner_->show();
        continue_->show();
        strip_->position(0, IMAGE_H + BANNER_H + BUTTON_ROW_H);
        window_->size(WIDTH, IMAGE_H + BANNER_H + BUTTON_ROW_H + STRIP_H);
        centre();
        window_->redraw();
    }

    void show_error(const std::string& text) {
        // The window must outlive the worker: once an error is on screen only
        // the user may dismiss it, so the Close posted when work() returns is
        // ignored from here on.
        error_shown_ = true;
        picture_->hide();
        strip_->hide();
        banner_->hide();
        continue_->hide();
        window_->border(1);
        window_->copy_label("SciQLop \xe2\x80\x94 startup failed");
        error_->buffer()->text(text.c_str());
        error_->show();
        copy_->show();
        quit_->show();
        window_->size(WIDTH, 458);
        centre();
        window_->redraw();
    }

    void close() {
        window_->hide();
        Fl::flush();
    }

    void run_with_worker(std::function<void()> work) override {
        window_->show();
        std::thread worker([this, work = std::move(work)] {
            work();
            post(PostKind::Close, {}, 0.0);
        });
        Fl::run();
        worker.join();
    }

    void post_phase(const std::string& text) override { post(PostKind::Phase, text, 0.0); }
    void post_detail(const std::string& text) override { post(PostKind::Detail, text, 0.0); }
    void post_progress(double percent) override { post(PostKind::Progress, {}, percent); }
    void post_warning(const std::string& message) override { post(PostKind::Warning, message, 0.0); }
    void post_error(const std::string& text) override { post(PostKind::Error, text, 0.0); }
    void dismiss() override { post(PostKind::Close, {}, 0.0); }

private:
    void build(const std::filesystem::path& splash_png) {
        window_ = new Fl_Window(WIDTH, IMAGE_H + STRIP_H, "SciQLop \xe2\x80\x94 starting");
        window_->color(rgb(13, 15, 20));
        window_->border(0);

        picture_ = new Fl_Box(0, 0, WIDTH, IMAGE_H);
        if (std::filesystem::is_regular_file(splash_png)) {
            image_ = new Fl_PNG_Image(splash_png.string().c_str());
            // Fl_Box draws an image at its own native pixel size otherwise —
            // the real splash art is larger than this box (1328x800 vs
            // 720x434), so without an explicit scale it would be cropped,
            // not shrunk to fit.
            image_->scale(WIDTH, IMAGE_H, 1, 1);
            picture_->image(image_);
        }

        banner_ = new WarningBanner(0, IMAGE_H, WIDTH, BANNER_H);
        banner_->hide();

        continue_ = new FlatButton(WIDTH - 130, IMAGE_H + BANNER_H + 10, 110, 30,
                                   "Continue", true);
        continue_->callback(on_continue, this);
        continue_->hide();

        strip_ = new CaptionStrip(0, IMAGE_H, WIDTH, STRIP_H);

        error_ = new Fl_Text_Display(PAD, PAD, WIDTH - 2 * PAD, 370);
        error_->buffer(new Fl_Text_Buffer());
        error_->color(rgb(22, 24, 30));
        error_->textcolor(rgb(255, 120, 120));
        error_->textfont(FL_COURIER);
        error_->textsize(12);
        error_->box(FL_FLAT_BOX);
        error_->hide();

        copy_ = new FlatButton(PAD, 406, 150, 32, "Copy to clipboard");
        quit_ = new FlatButton(PAD + 160, 406, 90, 32, "Quit", true);
        copy_->callback(on_copy, this);
        quit_->callback(on_quit, this);
        copy_->hide();
        quit_->hide();

        window_->end();
        centre();
    }

    void centre() {
        window_->position((Fl::w() - window_->w()) / 2, (Fl::h() - window_->h()) / 2);
    }

    void post(PostKind kind, const std::string& text, double value) {
        Fl::awake(apply, new Post{kind, text, value, this});
    }

    static void apply(void* data) {
        std::unique_ptr<Post> message(static_cast<Post*>(data));
        FltkUi* self = message->ui;
        switch (message->kind) {
            case PostKind::Phase:    self->set_phase(message->text); break;
            case PostKind::Detail:   self->set_detail(message->text); break;
            case PostKind::Progress: self->set_progress(message->value); break;
            case PostKind::Warning:  self->show_warning(message->text); break;
            case PostKind::Error:    self->show_error(message->text); break;
            case PostKind::Close:
                if (!self->error_shown_) self->close();
                break;
        }
    }

    static void on_continue(Fl_Widget*, void* data) {
        auto* self = static_cast<FltkUi*>(data);
        self->banner_->hide();
        self->continue_->hide();
        self->strip_->position(0, IMAGE_H);
        self->window_->size(WIDTH, IMAGE_H + STRIP_H);
        self->centre();
        self->window_->redraw();
    }

    static void on_copy(Fl_Widget*, void* data) {
        auto* self = static_cast<FltkUi*>(data);
        char* text = self->error_->buffer()->text();
        Fl::copy(text, static_cast<int>(std::string(text).size()), 1);
        free(text);
    }

    static void on_quit(Fl_Widget*, void* data) { static_cast<FltkUi*>(data)->close(); }

    Fl_Window* window_ = nullptr;
    Fl_PNG_Image* image_ = nullptr;
    Fl_Box* picture_ = nullptr;
    WarningBanner* banner_ = nullptr;
    CaptionStrip* strip_ = nullptr;
    FlatButton* continue_ = nullptr;
    FlatButton* copy_ = nullptr;
    FlatButton* quit_ = nullptr;
    Fl_Text_Display* error_ = nullptr;
    bool error_shown_ = false;
};

}  // namespace

std::unique_ptr<Ui> make_fltk_ui(const std::filesystem::path& splash_png) {
    return std::make_unique<FltkUi>(splash_png);
}

}  // namespace sciqlop
