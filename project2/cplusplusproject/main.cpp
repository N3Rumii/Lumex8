#include <QApplication>
#include <QMainWindow>
#include <QPushButton>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QFileDialog>
#include <QLabel>
#include <QListWidget>
#include <QMessageBox>
#include <QLineEdit>
#include <QStackedWidget>
#include <QCheckBox>
#include <QDialog>
#include <QSlider>
#include <QDragEnterEvent>
#include <QMimeData>
#include <QMap>
#include <QFileInfo>
#include <QUrl>
#include <QProgressBar>
#include <QShortcut>
#include <QInputDialog>
#include <QTimer>
#include <QSet>
#include <QSystemTrayIcon>
#include <QMenu>
#include <QClipboard>
#include <QStyle>
#include <QJsonDocument>
#include <QJsonObject>
#include <QCloseEvent>
#include <random>
#include <algorithm>
#include <memory>

#include "ImageVault.hpp"
#include "InfiniteViewer.hpp"
#include "DualViewer.hpp"

// --- CONFIG ---
static const QString CONFIG_PATH = "config.json";
static const QString DEFAULT_PIN = "0000";
static const QString DEFAULT_TITLE = "iRoll Secure Viewer";
static const int BLUR_FACTOR = 8;

// --- PIN LOCK DIALOG ---
class PinDialog : public QDialog {
public:
    PinDialog(const QString &storedPin, QWidget *parent = nullptr)
        : QDialog(parent), pin(storedPin)
    {
        setWindowTitle("Enter PIN");
        setFixedSize(250, 180);
        setStyleSheet("QDialog { background-color: #1e1e1e; } QLabel { color: #ccc; } "
                      "QLineEdit { background: #333; color: #fff; border: 1px solid #555; padding: 8px; font-size: 18px; } "
                      "QPushButton { background: #444; color: #fff; padding: 8px; border: none; }");

        QVBoxLayout *lay = new QVBoxLayout(this);
        QLabel *lbl = new QLabel("Enter 4-digit PIN:");
        lbl->setAlignment(Qt::AlignCenter);
        lay->addWidget(lbl);

        input = new QLineEdit();
        input->setEchoMode(QLineEdit::Password);
        input->setMaxLength(4);
        input->setAlignment(Qt::AlignCenter);
        lay->addWidget(input);

        errorLabel = new QLabel();
        errorLabel->setStyleSheet("color: #f44;");
        errorLabel->setAlignment(Qt::AlignCenter);
        errorLabel->hide();
        lay->addWidget(errorLabel);

        QPushButton *btn = new QPushButton("Unlock");
        btn->setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;");
        lay->addWidget(btn);

        connect(btn, &QPushButton::clicked, this, [this](){
            if (input->text() == pin || pin.isEmpty()) {
                accept();
            } else {
                errorLabel->setText("Wrong PIN");
                errorLabel->show();
                input->clear();
            }
        });
        connect(input, &QLineEdit::returnPressed, btn, [btn](){ btn->click(); });

        input->setFocus();
    }
private:
    QString pin;
    QLineEdit *input;
    QLabel *errorLabel;
};

// --- ENCODER POPUP (with dedup & batch subfolder) ---
class EncoderDialog : public QDialog {
public:
    EncoderDialog(QWidget *parent = nullptr) : QDialog(parent) {
        setWindowTitle("iRoll Encoder");
        resize(500, 320);
        QVBoxLayout *layout = new QVBoxLayout(this);

        // Input folder
        auto *h1 = new QHBoxLayout();
        inputEdit = new QLineEdit();
        inputEdit->setPlaceholderText("Select Image Folder...");
        QPushButton *btnIn = new QPushButton("Browse");
        h1->addWidget(inputEdit);
        h1->addWidget(btnIn);
        layout->addLayout(h1);

        // Output file
        auto *h2 = new QHBoxLayout();
        outputEdit = new QLineEdit();
        outputEdit->setPlaceholderText("Save as (.iroll)...");
        QPushButton *btnOut = new QPushButton("Browse");
        h2->addWidget(outputEdit);
        h2->addWidget(btnOut);
        layout->addLayout(h2);

        // Options row
        auto *hOpts = new QHBoxLayout();
        chkDedup = new QCheckBox("Skip duplicates");
        chkDedup->setStyleSheet("color: #ccc;");
        chkBatch = new QCheckBox("Batch subfolders");
        chkBatch->setStyleSheet("color: #ccc;");
        hOpts->addWidget(chkDedup);
        hOpts->addWidget(chkBatch);
        hOpts->addStretch();
        layout->addLayout(hOpts);

        progressBar = new QProgressBar();
        progressBar->setRange(0, 100);
        progressBar->setValue(0);
        progressBar->hide();
        layout->addWidget(progressBar);

        layout->addStretch();

        btnPack = new QPushButton("ENCRYPT & PACK");
        btnPack->setStyleSheet("background-color: #4CAF50; color: white; padding: 10px; font-weight: bold;");
        layout->addWidget(btnPack);

        connect(btnIn, &QPushButton::clicked, this, [this](){
            QString dir = QFileDialog::getExistingDirectory(this, "Select Folder");
            if (!dir.isEmpty()) inputEdit->setText(dir);
        });
        connect(btnOut, &QPushButton::clicked, this, [this](){
            QString file = QFileDialog::getSaveFileName(this, "Save Archive", "", "iRoll (*.iroll);;All Files (*)");
            if (!file.isEmpty()) {
                if (!file.contains('.')) file += ".iroll";
                outputEdit->setText(file);
            }
        });
        connect(chkBatch, &QCheckBox::toggled, this, [this](bool on){
            outputEdit->setEnabled(!on);
            outputEdit->setPlaceholderText(on ? "Output directory..." : "Save as (.iroll)...");
        });

        connect(btnPack, &QPushButton::clicked, this, [this](){
            if (inputEdit->text().isEmpty()) return;
            if (!chkBatch->isChecked() && outputEdit->text().isEmpty()) return;
            if (chkBatch->isChecked() && outputEdit->text().isEmpty()) {
                outputEdit->setText(inputEdit->text() + "_output");
            }

            btnPack->setEnabled(false);
            progressBar->setValue(0);
            progressBar->show();

            try {
                if (chkBatch->isChecked()) {
                    QDir().mkpath(outputEdit->text());
                    ImageVault::packSubfolders(inputEdit->text(), outputEdit->text(),
                        [this](int cur, int total) {
                            progressBar->setMaximum(total);
                            progressBar->setValue(cur);
                            QApplication::processEvents();
                        }, chkDedup->isChecked());
                    QMessageBox::information(this, "Done", "Batch packing complete!");
                } else {
                    ImageVault v;
                    v.pack(inputEdit->text(), outputEdit->text(),
                           [this](int cur, int total) {
                               progressBar->setMaximum(total);
                               progressBar->setValue(cur);
                               QApplication::processEvents();
                           }, chkDedup->isChecked());
                    QMessageBox::information(this, "Success", "Packed successfully!");
                }
                accept();
            } catch (const std::exception &e) {
                QMessageBox::critical(this, "Error", e.what());
                btnPack->setEnabled(true);
                progressBar->hide();
            }
        });
    }
private:
    QLineEdit *inputEdit, *outputEdit;
    QCheckBox *chkDedup, *chkBatch;
    QProgressBar *progressBar;
    QPushButton *btnPack;
};

// --- EXPORT DIALOG ---
class ExportDialog : public QDialog {
public:
    ExportDialog(QWidget *parent = nullptr) : QDialog(parent) {
        setWindowTitle("Export Images");
        resize(450, 150);
        QVBoxLayout *layout = new QVBoxLayout(this);
        QLabel *lbl = new QLabel("Extract all images from a loaded .iroll archive to a folder.");
        lbl->setWordWrap(true);
        layout->addWidget(lbl);
        auto *h1 = new QHBoxLayout();
        rollEdit = new QLineEdit(); rollEdit->setPlaceholderText("Select .iroll file...");
        QPushButton *btnRoll = new QPushButton("Browse");
        h1->addWidget(rollEdit); h1->addWidget(btnRoll);
        auto *h2 = new QHBoxLayout();
        dirEdit = new QLineEdit(); dirEdit->setPlaceholderText("Output directory...");
        QPushButton *btnDir = new QPushButton("Browse");
        h2->addWidget(dirEdit); h2->addWidget(btnDir);
        progressBar = new QProgressBar(); progressBar->setRange(0, 100); progressBar->hide();
        QPushButton *btnExtract = new QPushButton("EXTRACT ALL");
        btnExtract->setStyleSheet("background-color: #4CAF50; color: white; padding: 8px; font-weight: bold;");
        layout->addLayout(h1); layout->addLayout(h2);
        layout->addWidget(progressBar); layout->addWidget(btnExtract);

        connect(btnRoll, &QPushButton::clicked, this, [this](){
            QString f = QFileDialog::getOpenFileName(this, "Select iRoll", "", "iRoll (*.iroll);;All Files (*)");
            if (!f.isEmpty()) rollEdit->setText(f);
        });
        connect(btnDir, &QPushButton::clicked, this, [this](){
            QString d = QFileDialog::getExistingDirectory(this, "Select Output Directory");
            if (!d.isEmpty()) dirEdit->setText(d);
        });
        connect(btnExtract, &QPushButton::clicked, this, [this, btnExtract](){
            if (rollEdit->text().isEmpty() || dirEdit->text().isEmpty()) return;
            btnExtract->setEnabled(false);
            progressBar->setValue(0); progressBar->show();
            ImageVault v;
            if (!v.load_archive(rollEdit->text())) {
                QMessageBox::critical(this, "Error", v.get_last_error());
                btnExtract->setEnabled(true); progressBar->hide(); return;
            }
            int count = v.extract_all(dirEdit->text(), [this](int cur, int total) {
                progressBar->setMaximum(total); progressBar->setValue(cur);
                QApplication::processEvents();
            });
            QMessageBox::information(this, "Done",
                QString("Extracted %1 images to:\n%2").arg(count).arg(dirEdit->text()));
            accept();
        });
    }
private:
    QLineEdit *rollEdit, *dirEdit;
    QProgressBar *progressBar;
};

// --- SHORTCUTS DIALOG ---
class ShortcutsDialog : public QDialog {
public:
    ShortcutsDialog(QWidget *parent = nullptr) : QDialog(parent) {
        setWindowTitle("Keyboard Shortcuts");
        resize(400, 420);
        setStyleSheet("QDialog { background-color: #1e1e1e; color: #eee; } QLabel { color: #ccc; }");
        QVBoxLayout *layout = new QVBoxLayout(this);
        QLabel *title = new QLabel("KEYBOARD SHORTCUTS");
        title->setStyleSheet("font-weight: bold; font-size: 16px; color: #4CAF50;");
        title->setAlignment(Qt::AlignCenter);
        layout->addWidget(title); layout->addSpacing(15);
        auto add = [&](const QString &k, const QString &d) {
            QHBoxLayout *r = new QHBoxLayout();
            QLabel *kl = new QLabel(k);
            kl->setFixedWidth(150);
            kl->setStyleSheet("font-weight: bold; color: #fff; background: #333; padding: 4px 8px; border-radius: 4px;");
            r->addWidget(kl); r->addWidget(new QLabel(d)); r->addStretch();
            layout->addLayout(r);
        };
        add("Up Down Left Right", "Navigate images");
        add("F11", "Toggle fullscreen");
        add("Esc", "Exit fullscreen");
        add("Space", "Toggle slideshow");
        add("Ctrl + Wheel", "Zoom in / out");
        add("Ctrl + H", "Quick-hide window");
        add("Ctrl + F", "Focus search bar");
        add("Ctrl + C", "Copy image to clipboard");
        add("Ctrl + E", "Export dialog");
        add("S", "Toggle star/favorite");
        add("B", "Toggle blur viewer");
        add("?", "Show this panel");
        layout->addStretch();
        QPushButton *btn = new QPushButton("Close");
        btn->setStyleSheet("background-color: #444; color: white; padding: 8px;");
        connect(btn, &QPushButton::clicked, this, &QDialog::accept);
        layout->addWidget(btn);
    }
};

// --- CUSTOM PLAYLIST WIDGET ---
class PlaylistWidget : public QListWidget {
    Q_OBJECT
public:
    PlaylistWidget(QWidget *p = nullptr) : QListWidget(p) {
        setAcceptDrops(true);
        setDragDropMode(QAbstractItemView::InternalMove);
        setSelectionMode(QAbstractItemView::ExtendedSelection);
        setDragEnabled(true);
        setContextMenuPolicy(Qt::CustomContextMenu);
    }
protected:
    void dragEnterEvent(QDragEnterEvent *e) override {
        if (e->mimeData()->hasUrls()) e->acceptProposedAction();
        else QListWidget::dragEnterEvent(e);
    }
    void dragMoveEvent(QDragMoveEvent *e) override {
        if (e->mimeData()->hasUrls()) e->acceptProposedAction();
        else QListWidget::dragMoveEvent(e);
    }
    void dropEvent(QDropEvent *e) override {
        if (e->mimeData()->hasUrls()) {
            QStringList paths;
            for (const QUrl &u : e->mimeData()->urls()) {
                QString p = u.toLocalFile();
                if (p.endsWith(".iroll") || p.endsWith(".dat") || p.endsWith(".bin") || p.endsWith(".db"))
                    paths.append(p);
            }
            if (!paths.isEmpty()) emit filesDropped(paths);
        } else {
            QListWidget::dropEvent(e);
            emit orderChanged();
        }
    }
signals:
    void filesDropped(QStringList paths);
    void orderChanged();
};

// ========== MAIN VIEWER ==========
class MainWindow : public QMainWindow {
    Q_OBJECT
public:
    MainWindow(QWidget *parent = nullptr) : QMainWindow(parent) {
        loadConfig();
        if (requirePin) {
            PinDialog pd(storedPin);
            if (pd.exec() != QDialog::Accepted) {
                QTimer::singleShot(0, qApp, &QApplication::quit);
                return;
            }
        }
        setWindowTitle(windowTitleStr);
        resize(1200, 800);
        setStyleSheet("QMainWindow { background-color: #222; } "
                      "QListWidget { background-color: #1a1a1a; color: #ccc; border: none; font-size: 14px; outline: 0; } "
                      "QListWidget::item { padding: 5px; } "
                      "QListWidget::item:selected { background-color: #444; color: white; border-radius: 5px; } "
                      "QLabel { color: #eee; } QCheckBox { color: #eee; spacing: 5px; } "
                      "QSlider::handle:horizontal { background: #4CAF50; width: 15px; } "
                      "QLineEdit { background-color: #1a1a1a; color: #ccc; border: 1px solid #555; padding: 4px; }");
        setupUI();
        setupShortcuts();
        setupTray();
        // Start on blank viewer (index 1 = infinite, but empty)
        viewerStack->setCurrentIndex(1);
    }

    ~MainWindow() {
        for (auto it = loadedVaults.begin(); it != loadedVaults.end(); ++it)
            delete it.value();
    }

protected:
    void changeEvent(QEvent *event) override {
        if (event->type() == QEvent::ActivationChange) {
            if (!isActiveWindow() && dimOnUnfocus)
                setWindowOpacity(0.6);
            else
                setWindowOpacity(1.0);
        }
        QMainWindow::changeEvent(event);
    }

    void closeEvent(QCloseEvent *event) override {
        if (trayIcon && trayIcon->isVisible()) {
            hide();
            event->ignore();
        } else {
            event->accept();
        }
    }

private:
    // --- UI Members ---
    PlaylistWidget *leftPlaylist, *rightPlaylist;
    QStackedWidget *viewerStack;
    QListWidget *galleryList;
    InfiniteScrollWidget *infiniteReader;
    DualPaneWidget *dualViewer;
    QPushButton *btnDual, *btnShuffle, *btnStar;
    QCheckBox *chkSlide, *chkRandomSlide, *chkBlur;
    QSlider *slideTime;
    QLineEdit *searchBox;
    QLabel *zoomLabel, *infoOverlay, *starIndicator;
    QSystemTrayIcon *trayIcon = nullptr;

    QMap<QString, ImageVault*> loadedVaults;
    QSet<QString> favorites;
    int thumbnailLoadIndex = 0;
    double currentZoom = 1.0;
    bool dimOnUnfocus = true;

    std::vector<QString> singleFileList, leftFileList, rightFileList;

    // Config
    QString storedPin, windowTitleStr;
    bool requirePin = false;

    void loadConfig() {
        QFile f(CONFIG_PATH);
        if (f.open(QIODevice::ReadOnly)) {
            QJsonDocument doc = QJsonDocument::fromJson(f.readAll());
            QJsonObject o = doc.object();
            storedPin = o.value("pin").toString(DEFAULT_PIN);
            requirePin = o.value("require_pin").toBool(false);
            windowTitleStr = o.value("window_title").toString(DEFAULT_TITLE);
            dimOnUnfocus = o.value("dim_on_unfocus").toBool(true);
            if (storedPin.isEmpty()) storedPin = DEFAULT_PIN;
            f.close();
        } else {
            storedPin = DEFAULT_PIN;
            windowTitleStr = DEFAULT_TITLE;
        }
    }

    void saveConfig() {
        QJsonObject o;
        o["pin"] = storedPin;
        o["require_pin"] = requirePin;
        o["window_title"] = windowTitleStr;
        o["dim_on_unfocus"] = dimOnUnfocus;
        QFile f(CONFIG_PATH);
        if (f.open(QIODevice::WriteOnly)) {
            f.write(QJsonDocument(o).toJson());
            f.close();
        }
    }

    // PlaylistWidget defined at file scope above

    void setupUI() {
        QWidget *central = new QWidget(this);
        QHBoxLayout *mainLayout = new QHBoxLayout(central);
        mainLayout->setContentsMargins(0,0,0,0); mainLayout->setSpacing(0);

        // Sidebar
        QWidget *sidebar = new QWidget();
        sidebar->setFixedWidth(280);
        sidebar->setStyleSheet("background-color: #181818; border-right: 1px solid #333;");
        QVBoxLayout *sideLayout = new QVBoxLayout(sidebar);

        searchBox = new QLineEdit();
        searchBox->setPlaceholderText("Search... (Ctrl+F)");
        searchBox->setClearButtonEnabled(true);
        sideLayout->addWidget(searchBox);

        // LEFT PANE
        QLabel *lblL = new QLabel("LEFT PANE");
        lblL->setStyleSheet("font-weight: bold; color: #888; margin-top: 6px;");
        sideLayout->addWidget(lblL);
        leftPlaylist = new PlaylistWidget();
        sideLayout->addWidget(leftPlaylist);
        QLabel *hintL = new QLabel("Drag & drop files here");
        hintL->setStyleSheet("color: #555; font-style: italic; font-size: 11px;");
        hintL->setAlignment(Qt::AlignCenter);
        sideLayout->addWidget(hintL);
        QPushButton *btnAddL = new QPushButton("Add to Left");
        sideLayout->addWidget(btnAddL);
        QWidget *sep = new QWidget(); sep->setFixedHeight(1);
        sep->setStyleSheet("background-color: #333;");
        sideLayout->addWidget(sep); sideLayout->addSpacing(8);

        // RIGHT PANE
        QLabel *lblR = new QLabel("RIGHT PANE");
        lblR->setStyleSheet("font-weight: bold; color: #888;");
        sideLayout->addWidget(lblR);
        rightPlaylist = new PlaylistWidget();
        sideLayout->addWidget(rightPlaylist);
        QLabel *hintR = new QLabel("Drag & drop files here");
        hintR->setStyleSheet("color: #555; font-style: italic; font-size: 11px;");
        hintR->setAlignment(Qt::AlignCenter);
        sideLayout->addWidget(hintR);
        QPushButton *btnAddR = new QPushButton("Add to Right");
        sideLayout->addWidget(btnAddR);
        QWidget *sep2 = new QWidget(); sep2->setFixedHeight(1);
        sep2->setStyleSheet("background-color: #333;");
        sideLayout->addWidget(sep2); sideLayout->addSpacing(8);

        // Show hidden checkbox
        QCheckBox *chkShowHidden = new QCheckBox("Show hidden");
        chkShowHidden->setStyleSheet("color: #888;");
        sideLayout->addWidget(chkShowHidden);

        QPushButton *btnEncoder = new QPushButton("New Encoder");
        QPushButton *btnExport = new QPushButton("Export Images");
        sideLayout->addWidget(btnEncoder);
        sideLayout->addWidget(btnExport);
        mainLayout->addWidget(sidebar);

        // Content area
        QWidget *contentArea = new QWidget();
        QVBoxLayout *contentLayout = new QVBoxLayout(contentArea);
        contentLayout->setContentsMargins(0,0,0,0);

        // Toolbar
        QWidget *toolbar = new QWidget();
        toolbar->setStyleSheet("background-color: #222; border-bottom: 1px solid #333;");
        toolbar->setFixedHeight(50);
        QHBoxLayout *tl = new QHBoxLayout(toolbar);

        QPushButton *btnGrid = new QPushButton("Grid");
        QCheckBox *chkFit = new QCheckBox("Fit Screen");
        QCheckBox *chkSnap = new QCheckBox("Snap");
        QPushButton *btnFull = new QPushButton("Fullscreen");
        QLabel *lblSlide = new QLabel("Slide:");
        chkSlide = new QCheckBox("Auto");
        chkRandomSlide = new QCheckBox("Random");
        chkRandomSlide->setStyleSheet("color: #888;");
        slideTime = new QSlider(Qt::Horizontal);
        slideTime->setRange(1, 10); slideTime->setValue(3); slideTime->setFixedWidth(80);
        btnDual = new QPushButton("Dual Pane"); btnDual->setCheckable(true);
        btnShuffle = new QPushButton("Shuffle");
        btnStar = new QPushButton("☆");
        btnStar->setCheckable(true);
        btnStar->setStyleSheet("QPushButton { color: #FFD700; font-size: 16px; } QPushButton:checked { color: #FFD700; }");
        chkBlur = new QCheckBox("Blur");
        chkBlur->setStyleSheet("color: #888;");
        zoomLabel = new QLabel("100%");
        zoomLabel->setStyleSheet("color: #4CAF50; font-weight: bold; min-width: 50px;");
        starIndicator = new QLabel();
        starIndicator->setStyleSheet("color: #FFD700; font-size: 14px;");

        tl->addWidget(btnGrid); tl->addWidget(chkFit); tl->addWidget(chkSnap);
        tl->addWidget(btnFull); tl->addSpacing(20);
        tl->addWidget(lblSlide); tl->addWidget(chkSlide); tl->addWidget(chkRandomSlide);
        tl->addWidget(slideTime); tl->addSpacing(10);
        tl->addWidget(btnDual); tl->addSpacing(10);
        tl->addWidget(btnStar); tl->addWidget(starIndicator); tl->addSpacing(10);
        tl->addWidget(chkBlur); tl->addStretch();
        tl->addWidget(zoomLabel); tl->addWidget(btnShuffle);
        contentLayout->addWidget(toolbar);

        // Viewer
        QWidget *vc = new QWidget();
        QVBoxLayout *vcl = new QVBoxLayout(vc);
        vcl->setContentsMargins(0,0,0,0);
        viewerStack = new QStackedWidget();
        galleryList = new QListWidget();
        galleryList->setViewMode(QListWidget::IconMode);
        galleryList->setIconSize(QSize(140, 140));
        galleryList->setGridSize(QSize(160, 160));
        galleryList->setResizeMode(QListWidget::Adjust);
        galleryList->setMovement(QListView::Static);
        galleryList->setStyleSheet("background-color: #222;");
        infiniteReader = new InfiniteScrollWidget();
        infiniteReader->setVaults(&loadedVaults);
        dualViewer = new DualPaneWidget();
        dualViewer->setVaults(&loadedVaults);
        viewerStack->addWidget(galleryList);    // 0
        viewerStack->addWidget(infiniteReader); // 1
        viewerStack->addWidget(dualViewer);     // 2

        infoOverlay = new QLabel(viewerStack);
        infoOverlay->setStyleSheet("background-color: rgba(0,0,0,180); color: #ccc; padding: 8px 12px; border-radius: 6px; font-size: 12px;");
        infoOverlay->hide();
        infoOverlay->setAttribute(Qt::WA_TransparentForMouseEvents);

        vcl->addWidget(viewerStack);
        contentLayout->addWidget(vc);
        mainLayout->addWidget(contentArea);
        setCentralWidget(central);

        // ---- Connections ----
        connect(btnEncoder, &QPushButton::clicked, this, [this](){ EncoderDialog(this).exec(); });
        connect(btnExport, &QPushButton::clicked, this, [this](){ ExportDialog(this).exec(); });
        connect(btnAddL, &QPushButton::clicked, this, [this](){ openFileDialog(); });
        connect(btnAddR, &QPushButton::clicked, this, [this](){ openFileDialog(); });
        connect(leftPlaylist, &PlaylistWidget::filesDropped, this, &MainWindow::addRollsToSession);
        connect(rightPlaylist, &PlaylistWidget::filesDropped, this, &MainWindow::addRollsToSession);
        connect(leftPlaylist, &PlaylistWidget::orderChanged, this, &MainWindow::rebuildActiveList);
        connect(rightPlaylist, &PlaylistWidget::orderChanged, this, &MainWindow::rebuildActiveList);
        connect(leftPlaylist, &QListWidget::itemChanged, this, &MainWindow::rebuildActiveList);
        connect(rightPlaylist, &QListWidget::itemChanged, this, &MainWindow::rebuildActiveList);

        // Right-click context menu for hide
        connect(leftPlaylist, &QListWidget::customContextMenuRequested, this, [this](const QPoint &pos){
            showPlaylistContextMenu(leftPlaylist, pos);
        });
        connect(rightPlaylist, &QListWidget::customContextMenuRequested, this, [this](const QPoint &pos){
            showPlaylistContextMenu(rightPlaylist, pos);
        });

        // Show hidden toggle
        connect(chkShowHidden, &QCheckBox::toggled, this, [this](bool show){
            showHiddenItems(leftPlaylist, show);
            showHiddenItems(rightPlaylist, show);
            rebuildActiveList();
        });

        connect(btnGrid, &QPushButton::clicked, this, [this](){ viewerStack->setCurrentIndex(0); infoOverlay->hide(); });
        connect(galleryList, &QListWidget::itemClicked, this, [this](QListWidgetItem *item){
            int idx = galleryList->row(item);
            if (btnDual->isChecked()) {
                viewerStack->setCurrentIndex(2);
                dualViewer->jumpToSpecificIndex(idx);
                dualViewer->grabFocus();
            } else {
                viewerStack->setCurrentIndex(1);
                infiniteReader->jumpToSpecificIndex(idx);
                infiniteReader->setFocus();
            }
            pauseSlideshow();
        });
        connect(chkFit, &QCheckBox::toggled, this, [this](bool c){
            if (btnDual->isChecked()) dualViewer->setFitToScreen(c);
            else infiniteReader->setFitToScreen(c);
        });
        connect(chkSnap, &QCheckBox::toggled, this, [this](bool c){
            if (btnDual->isChecked()) dualViewer->setSnapToGrid(c);
            else infiniteReader->setSnapToGrid(c);
        });
        connect(btnFull, &QPushButton::clicked, this, [this](){
            if(isFullScreen()) showNormal(); else showFullScreen();
        });
        connect(chkSlide, &QCheckBox::toggled, this, [this](bool c){
            if (btnDual->isChecked()) dualViewer->toggleSlideshow(c, slideTime->value());
            else infiniteReader->toggleSlideshow(c, slideTime->value());
        });
        connect(chkRandomSlide, &QCheckBox::toggled, this, [this](bool c){
            if (btnDual->isChecked()) {
                dualViewer->left()->setRandomSlideshow(c);
                dualViewer->right()->setRandomSlideshow(c);
            } else {
                infiniteReader->setRandomSlideshow(c);
            }
        });
        connect(slideTime, &QSlider::valueChanged, this, [this](int v){
            if (btnDual->isChecked()) dualViewer->updateSlideInterval(v);
            else infiniteReader->updateSlideInterval(v);
        });
        connect(chkBlur, &QCheckBox::toggled, this, [this](bool c){
            if (btnDual->isChecked()) {
                dualViewer->left()->setBlurImages(c);
                dualViewer->right()->setBlurImages(c);
            } else {
                infiniteReader->setBlurImages(c);
            }
        });
        connect(infiniteReader, &InfiniteScrollWidget::userNavigated, this, &MainWindow::pauseSlideshow);
        connect(dualViewer, &DualPaneWidget::userNavigated, this, &MainWindow::pauseSlideshow);
        connect(btnDual, &QPushButton::toggled, this, [this](bool){ rebuildActiveList(); });
        connect(btnShuffle, &QPushButton::clicked, this, &MainWindow::shuffleImages);
        connect(btnStar, &QPushButton::toggled, this, &MainWindow::toggleStarFilter);
        connect(searchBox, &QLineEdit::textChanged, this, &MainWindow::applySearchFilter);

        viewerStack->installEventFilter(this);
        infiniteReader->setMouseTracking(true);
        infiniteReader->installEventFilter(this);
        dualViewer->installEventFilter(this);
    }

    void setupShortcuts() {
        new QShortcut(QKeySequence("Ctrl+F"), this, [this](){ searchBox->setFocus(); searchBox->selectAll(); });
        new QShortcut(QKeySequence("Ctrl+E"), this, [this](){ ExportDialog(this).exec(); });
        new QShortcut(QKeySequence("?"), this, [this](){ ShortcutsDialog(this).exec(); });
        new QShortcut(QKeySequence("Ctrl+C"), this, [this](){ copyImageToClipboard(); });
        new QShortcut(QKeySequence("Ctrl+H"), this, [this](){ quickHide(); });
        new QShortcut(QKeySequence("B"), this, [this](){ chkBlur->toggle(); });
        new QShortcut(QKeySequence("S"), this, [this](){ toggleFavorite(); });
        new QShortcut(QKeySequence("Space"), this, [this](){ chkSlide->setChecked(!chkSlide->isChecked()); });
    }

    void setupTray() {
        trayIcon = new QSystemTrayIcon(this);
        trayIcon->setIcon(style()->standardIcon(QStyle::SP_ComputerIcon));
        QMenu *trayMenu = new QMenu(this);
        QAction *showAction = trayMenu->addAction("Show");
        connect(showAction, &QAction::triggered, this, [this](){ show(); raise(); activateWindow(); });
        QAction *quitAction = trayMenu->addAction("Quit");
        connect(quitAction, &QAction::triggered, qApp, &QApplication::quit);
        trayIcon->setContextMenu(trayMenu);
        connect(trayIcon, &QSystemTrayIcon::activated, this, [this](QSystemTrayIcon::ActivationReason r){
            if (r == QSystemTrayIcon::Trigger || r == QSystemTrayIcon::DoubleClick) {
                show(); raise(); activateWindow();
            }
        });
        trayIcon->show();
    }

    void quickHide() {
        if (isVisible()) { hide(); }
        else { show(); raise(); activateWindow(); }
    }

    void copyImageToClipboard() {
        InfiniteScrollWidget *v = btnDual->isChecked() ? dualViewer->left() : infiniteReader;
        if (!v) return;
        QPixmap pix = v->getCurrentPixmap();
        if (!pix.isNull()) {
            QApplication::clipboard()->setPixmap(pix);
        }
    }

    void toggleFavorite() {
        InfiniteScrollWidget *v = btnDual->isChecked() ? dualViewer->left() : infiniteReader;
        if (!v) return;
        QString id = v->getCurrentFileID();
        if (id.isEmpty()) return;
        if (favorites.contains(id)) favorites.remove(id);
        else favorites.insert(id);
        updateStarIndicator();
    }

    void toggleStarFilter(bool on) {
        rebuildActiveList();
        updateStarIndicator();
    }

    void updateStarIndicator() {
        InfiniteScrollWidget *v = btnDual->isChecked() ? dualViewer->left() : infiniteReader;
        if (!v) { starIndicator->setText(""); return; }
        QString id = v->getCurrentFileID();
        if (id.isEmpty()) { starIndicator->setText(""); return; }
        starIndicator->setText(favorites.contains(id) ? "★" : "☆");
        btnStar->setChecked(favorites.contains(id));
    }

    void showPlaylistContextMenu(PlaylistWidget *pl, const QPoint &pos) {
        QListWidgetItem *item = pl->itemAt(pos);
        if (!item) return;
        QMenu menu;
        QAction *hideAction = menu.addAction("Hide");
        QAction *showAction = menu.addAction("Show All Hidden");
        QAction *chosen = menu.exec(pl->viewport()->mapToGlobal(pos));
        if (chosen == hideAction) {
            item->setData(Qt::UserRole + 1, true); // hidden flag
            item->setHidden(true);
            rebuildActiveList();
        } else if (chosen == showAction) {
            showHiddenItems(leftPlaylist, true);
            showHiddenItems(rightPlaylist, true);
            rebuildActiveList();
        }
    }

    void showHiddenItems(PlaylistWidget *pl, bool show) {
        for (int i = 0; i < pl->count(); i++) {
            QListWidgetItem *item = pl->item(i);
            bool hidden = item->data(Qt::UserRole + 1).toBool();
            if (hidden) item->setHidden(!show);
        }
    }

    void openFileDialog() {
        QString file = QFileDialog::getOpenFileName(this, "Open Archive", "",
            "Archives (*.iroll *.dat *.bin *.db);;All Files (*)");
        if (!file.isEmpty()) addRollsToSession({file});
    }

    bool eventFilter(QObject *obj, QEvent *event) override {
        if (obj == infiniteReader || obj == dualViewer || obj == viewerStack) {
            if (event->type() == QEvent::Enter || event->type() == QEvent::MouseMove)
                updateInfoOverlay();
            else if (event->type() == QEvent::Leave)
                infoOverlay->hide();
        }
        if (event->type() == QEvent::Wheel) {
            QWheelEvent *we = static_cast<QWheelEvent*>(event);
            if (we->modifiers() & Qt::ControlModifier) {
                double nz = currentZoom * (we->angleDelta().y() > 0 ? 1.15 : 0.85);
                if (nz < 0.25) nz = 0.25; if (nz > 4.0) nz = 4.0;
                setZoom(nz);
                return true;
            }
        }
        return QMainWindow::eventFilter(obj, event);
    }

    void setZoom(double f) {
        currentZoom = f;
        if (btnDual->isChecked()) dualViewer->setZoom(f);
        else infiniteReader->setZoom(f);
        zoomLabel->setText(QString("%1%").arg(static_cast<int>(f * 100)));
    }

    void updateInfoOverlay() {
        if (viewerStack->currentIndex() == 0) { infoOverlay->hide(); return; }
        InfiniteScrollWidget *v = btnDual->isChecked() ? dualViewer->left() : infiniteReader;
        if (!v) return;
        int idx = v->getCurrentIndex();
        const std::vector<QString> &files = btnDual->isChecked() ? leftFileList : singleFileList;
        if (idx < 0 || idx >= static_cast<int>(files.size())) { infoOverlay->hide(); return; }
        QString fid = files[idx];
        QStringList parts = fid.split("||");
        if (parts.size() < 2) { infoOverlay->hide(); return; }
        QString vp = parts[0];
        std::string fn = parts[1].toStdString();
        if (!loadedVaults.contains(vp)) { infoOverlay->hide(); return; }
        ImageVault *iv = loadedVaults[vp];
        qint64 sz = iv->get_file_original_size(fn);
        QPixmap pix = v->getCurrentPixmap();
        QString ss;
        if (sz >= 1024*1024) ss = QString::number(sz/(1024.0*1024.0),'f',1) + " MB";
        else if (sz >= 1024) ss = QString::number(sz/1024.0,'f',1) + " KB";
        else ss = QString::number(sz) + " B";
        QString text = QString("%1\n%2 x %3  |  %4")
            .arg(QString::fromStdString(fn))
            .arg(pix.isNull()?0:pix.width()).arg(pix.isNull()?0:pix.height()).arg(ss);
        infoOverlay->setText(text); infoOverlay->adjustSize();
        QWidget *pw = infoOverlay->parentWidget();
        infoOverlay->move(12, pw->height() - infoOverlay->height() - 12);
        infoOverlay->show();
        updateStarIndicator();
    }

    void pauseSlideshow() {
        if (chkSlide->isChecked()) {
            chkSlide->setChecked(false);
            if (btnDual->isChecked()) dualViewer->stopSlideshow();
            else infiniteReader->stopSlideshow();
        }
    }

    void applySearchFilter(const QString &text) {
        auto flt = [&](PlaylistWidget *pl) {
            for (int i = 0; i < pl->count(); i++) {
                QListWidgetItem *item = pl->item(i);
                bool match = text.isEmpty() || item->text().contains(text, Qt::CaseInsensitive);
                if (!match) item->setHidden(true);
                else if (!item->data(Qt::UserRole + 1).toBool()) item->setHidden(false);
            }
        };
        flt(leftPlaylist); flt(rightPlaylist);
    }

    void addRollsToSession(const QStringList &paths) {
        bool changed = false;
        for (const QString &path : paths) {
            if (loadedVaults.contains(path)) continue;
            ImageVault *v = new ImageVault();
            if (!v->load_archive(path)) { delete v; continue; }
            loadedVaults.insert(path, v); changed = true;
        }
        for (const QString &path : paths) {
            if (!loadedVaults.contains(path)) continue;
            QFileInfo fi(path);
            auto add = [&](PlaylistWidget *pl) {
                QListWidgetItem *item = new QListWidgetItem(fi.fileName());
                item->setFlags(item->flags() | Qt::ItemIsUserCheckable | Qt::ItemIsEnabled | Qt::ItemIsSelectable);
                item->setCheckState(Qt::Checked);
                item->setData(Qt::UserRole, path);
                pl->addItem(item);
            };
            add(leftPlaylist); add(rightPlaylist);
        }
        applySearchFilter(searchBox->text());
        if (changed) rebuildActiveList();
    }

    std::vector<QString> collect(PlaylistWidget *pl) {
        std::vector<QString> r;
        for (int i = 0; i < pl->count(); i++) {
            QListWidgetItem *item = pl->item(i);
            if (item->isHidden()) continue;
            if (item->checkState() != Qt::Checked) continue;
            QString path = item->data(Qt::UserRole).toString();
            if (!loadedVaults.contains(path)) continue;
            ImageVault *v = loadedVaults[path];
            for (const auto &fn : v->get_file_list()) {
                QString fid = path + "||" + QString::fromStdString(fn);
                if (btnStar->isChecked() && !favorites.contains(fid)) continue;
                r.push_back(fid);
            }
        }
        return r;
    }

    void rebuildActiveList() {
        galleryList->setUpdatesEnabled(false);
        galleryList->clear();
        QSet<QString> seen;
        auto addG = [&](PlaylistWidget *pl) {
            for (int i = 0; i < pl->count(); i++) {
                QListWidgetItem *item = pl->item(i);
                if (item->isHidden()) continue;
                if (item->checkState() != Qt::Checked) continue;
                QString path = item->data(Qt::UserRole).toString();
                if (!loadedVaults.contains(path)) continue;
                ImageVault *v = loadedVaults[path];
                for (const auto &fn : v->get_file_list()) {
                    QString n = QString::fromStdString(fn);
                    QString fid = path + "||" + n;
                    if (seen.contains(fid)) continue;
                    if (btnStar->isChecked() && !favorites.contains(fid)) continue;
                    seen.insert(fid);
                    QListWidgetItem *gi = new QListWidgetItem(QIcon(), n);
                    gi->setData(Qt::UserRole, fid);
                    galleryList->addItem(gi);
                }
            }
        };
        addG(leftPlaylist); addG(rightPlaylist);
        galleryList->setUpdatesEnabled(true);

        if (btnDual->isChecked()) {
            leftFileList = collect(leftPlaylist);
            rightFileList = collect(rightPlaylist);
            dualViewer->setLeftImages(leftFileList);
            dualViewer->setRightImages(rightFileList);
            viewerStack->setCurrentIndex(2);
        } else {
            singleFileList = collect(leftPlaylist);
            infiniteReader->loadImages(singleFileList);
            viewerStack->setCurrentIndex(1);
        }
        thumbnailLoadIndex = 0;
        loadNextBatchOfThumbnails();
    }

    void loadNextBatchOfThumbnails() {
        int batch = 10, max = galleryList->count(), done = 0;
        while (done < batch && thumbnailLoadIndex < max) {
            QListWidgetItem *item = galleryList->item(thumbnailLoadIndex);
            QString fid = item->data(Qt::UserRole).toString();
            (void)QtConcurrent::run([this, fid]() {
                QStringList p = fid.split("||");
                if (p.size() < 2) return;
                QString vp = p[0]; std::string fn = p[1].toStdString();
                if (loadedVaults.contains(vp)) {
                    auto data = loadedVaults[vp]->get_file_data(fn);
                    if (!data.empty()) {
                        QImage img;
                        if (img.loadFromData((const uchar*)data.data(), data.size())) {
                            QPixmap thumb = QPixmap::fromImage(img.scaled(140,140,Qt::KeepAspectRatio,Qt::FastTransformation));
                            // Blur thumbnails
                            if (chkBlur->isChecked()) {
                                thumb = thumb.scaled(thumb.size()/BLUR_FACTOR, Qt::KeepAspectRatio, Qt::FastTransformation);
                                thumb = thumb.scaled(140, 140, Qt::KeepAspectRatio, Qt::FastTransformation);
                            }
                            QMetaObject::invokeMethod(this, [this, fid, thumb](){
                                QString nm = fid.split("||").last();
                                auto items = galleryList->findItems(nm, Qt::MatchExactly);
                                for (auto *it : items)
                                    if (it->data(Qt::UserRole).toString() == fid) it->setIcon(QIcon(thumb));
                            });
                        }
                    }
                }
            });
            thumbnailLoadIndex++; done++;
        }
        if (thumbnailLoadIndex < max)
            QTimer::singleShot(50, this, &MainWindow::loadNextBatchOfThumbnails);
    }

    std::vector<QString> shufflePerVault(PlaylistWidget *pl) {
        std::random_device rd; std::mt19937 g(rd());
        std::vector<QString> vp;
        for (int i = 0; i < pl->count(); i++) {
            QListWidgetItem *item = pl->item(i);
            if (item->isHidden() || item->checkState() != Qt::Checked) continue;
            QString path = item->data(Qt::UserRole).toString();
            if (loadedVaults.contains(path)) vp.push_back(path);
        }
        std::vector<QString> result;
        for (const QString &p : vp) {
            auto files = loadedVaults[p]->get_file_list();
            std::shuffle(files.begin(), files.end(), g);
            for (const auto &f : files) {
                QString fid = p + "||" + QString::fromStdString(f);
                if (btnStar->isChecked() && !favorites.contains(fid)) continue;
                result.push_back(fid);
            }
        }
        return result;
    }

    void shuffleImages() {
        if (btnDual->isChecked()) {
            leftFileList = shufflePerVault(leftPlaylist);
            rightFileList = shufflePerVault(rightPlaylist);
            dualViewer->setLeftImages(leftFileList);
            dualViewer->setRightImages(rightFileList);
        } else {
            singleFileList = shufflePerVault(leftPlaylist);
            infiniteReader->loadImages(singleFileList);
        }
    }
};

int main(int argc, char *argv[]) {
    QApplication app(argc, argv);
    app.setStyle("Fusion");
    app.setQuitOnLastWindowClosed(false);
    MainWindow w;
    w.show();
    return app.exec();
}
#include "main.moc"
