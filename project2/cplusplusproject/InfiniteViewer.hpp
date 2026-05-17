#ifndef INFINITE_VIEWER_HPP
#define INFINITE_VIEWER_HPP

#include <QWidget>
#include <QPainter>
#include <QWheelEvent>
#include <QKeyEvent>
#include <QTimer>
#include <QMap>
#include <QCache>
#include <QtConcurrent>
#include "ImageVault.hpp"

const int CACHE_SIZE = 50;
const int SCROLL_SPEED = 40;
const QColor BG_COLOR("#222222");

class InfiniteScrollWidget : public QWidget {
    Q_OBJECT

public:
    explicit InfiniteScrollWidget(QWidget *parent = nullptr) : QWidget(parent) {
        setMouseTracking(true);
        setFocusPolicy(Qt::StrongFocus);

        QPalette pal = palette();
        pal.setColor(QPalette::Window, BG_COLOR);
        setAutoFillBackground(true);
        setPalette(pal);

        checkTimer = new QTimer(this);
        connect(checkTimer, &QTimer::timeout, this, [this]() { update(); });
        checkTimer->start(16);

        slideTimer = new QTimer(this);
        connect(slideTimer, &QTimer::timeout, this, [this]() {
            jumpToIndex(1);
        });
    }

    void setVaults(QMap<QString, ImageVault*> *vMap) {
        activeVaults = vMap;
    }

    void loadImages(const std::vector<QString>& files) {
        fileList = files;
        scrollY = 0;
        imageCache.clear();
        imageHeights.clear();
        pendingRequests.clear();
        currentRenderIndex = 0;
        if (!files.empty()) {
            // Start at random position if randomSlideshow is on
            if (randomSlideshow && randomEngine) {
                std::uniform_int_distribution<int> dist(0, static_cast<int>(files.size()) - 1);
                currentRenderIndex = dist(*randomEngine);
            }
        }
        update();
        setFocus();
    }

    void setFitToScreen(bool enable) {
        fitScreen = enable;
        imageHeights.clear();
        imageCache.clear();
        pendingRequests.clear();
        update();
    }

    void setSnapToGrid(bool enable) {
        snapToGrid = enable;
    }

    void setBlurImages(bool enable) {
        blurEnabled = enable;
        imageCache.clear();
        update();
    }

    void toggleSlideshow(bool active, int intervalSeconds) {
        if (active) slideTimer->start(intervalSeconds * 1000);
        else slideTimer->stop();
    }

    void updateSlideInterval(int seconds) {
        if (slideTimer->isActive()) slideTimer->start(seconds * 1000);
    }

    bool isSlideshowActive() const {
        return slideTimer->isActive();
    }

    void stopSlideshow() {
        slideTimer->stop();
    }

    void setRandomSlideshow(bool enable) {
        randomSlideshow = enable;
    }

    void setZoom(double factor) {
        if (factor < 0.25) factor = 0.25;
        if (factor > 4.0) factor = 4.0;
        zoomFactor = factor;
        imageHeights.clear();
        imageCache.clear();
        pendingRequests.clear();
        update();
    }

    double getZoom() const { return zoomFactor; }

    QPixmap getCurrentPixmap() const {
        if (currentRenderIndex >= 0 && currentRenderIndex < static_cast<int>(fileList.size())) {
            if (imageCache.contains(currentRenderIndex))
                return *imageCache.object(currentRenderIndex);
        }
        return QPixmap();
    }

    int getCurrentIndex() const { return currentRenderIndex; }

    QString getCurrentFileID() const {
        if (currentRenderIndex >= 0 && currentRenderIndex < static_cast<int>(fileList.size()))
            return fileList[currentRenderIndex];
        return QString();
    }

    void jumpToSpecificIndex(int index) {
        if (fileList.empty()) return;

        int sz = static_cast<int>(fileList.size());
        index = ((index % sz) + sz) % sz;

        int viewW = width();
        int viewH = height();

        qint64 targetY = 0;
        for (int i = 0; i < index; i++) {
            targetY += getEstimatedHeight(i, viewW, viewH);
        }

        qint64 totalCycleH = 0;
        for (int i = 0; i < sz; i++) totalCycleH += getEstimatedHeight(i, viewW, viewH);
        if (totalCycleH > 0) {
            qint64 loopCount = scrollY / totalCycleH;
            scrollY = (loopCount * totalCycleH) + targetY;
        } else {
            scrollY = targetY;
        }
        currentRenderIndex = index;
        update();

        emit jumpedToIndex(index);
    }

    void setScrollY(qint64 y) {
        scrollY = y;
        update();
    }

signals:
    void scrolled(qint64 newY);
    void jumpedToIndex(int index);
    void userNavigated();

protected:
    void keyPressEvent(QKeyEvent *event) override {
        if (fileList.empty()) {
            QWidget::keyPressEvent(event);
            return;
        }

        if (event->key() == Qt::Key_Escape) {
            if (window()->isFullScreen()) window()->showNormal();
            return;
        }

        if (event->key() == Qt::Key_F11) {
            if (window()->isFullScreen()) window()->showNormal();
            else window()->showFullScreen();
            return;
        }

        int step = 0;
        if (event->key() == Qt::Key_Up || event->key() == Qt::Key_Left) step = -1;
        else if (event->key() == Qt::Key_Down || event->key() == Qt::Key_Right) step = 1;

        if (step != 0) {
            if (snapToGrid) {
                jumpToIndex(currentRenderIndex + step);
            } else {
                scrollY += (step * 100);
                update();
                emit scrolled(scrollY);
            }
            emit userNavigated();
        } else {
            QWidget::keyPressEvent(event);
        }
    }

    void wheelEvent(QWheelEvent *event) override {
        int delta = event->angleDelta().y();
        if (delta == 0) return;

        int steps = (delta > 0) ? -SCROLL_SPEED : SCROLL_SPEED;
        scrollY += steps;
        update();
        emit scrolled(scrollY);
        emit userNavigated();
    }

    void resizeEvent(QResizeEvent *event) override {
        Q_UNUSED(event);
        imageHeights.clear();
        update();
    }

    void paintEvent(QPaintEvent *event) override {
        Q_UNUSED(event);
        QPainter painter(this);
        if (fileList.empty()) {
            painter.setPen(Qt::white);
            painter.drawText(rect(), Qt::AlignCenter,
                             "No active rolls selected.\n"
                             "Check the boxes in the playlist.");
            return;
        }

        int viewW = width();
        int viewH = height();
        int sz = static_cast<int>(fileList.size());

        qint64 totalCycleH = 0;
        for (int i = 0; i < sz; i++) totalCycleH += getEstimatedHeight(i, viewW, viewH);
        if (totalCycleH == 0) return;

        if (scrollY < 0) {
            scrollY = totalCycleH - ((-scrollY) % totalCycleH);
            if (scrollY == totalCycleH) scrollY = 0;
        }
        qint64 effectiveY = scrollY % totalCycleH;

        int currentIndex = 0;
        qint64 accumY = 0;

        for (int i = 0; i < sz; i++) {
            int h = getEstimatedHeight(i, viewW, viewH);
            if (accumY + h > effectiveY) {
                currentIndex = i;
                break;
            }
            accumY += h;
        }
        currentRenderIndex = currentIndex;

        int drawY = static_cast<int>(accumY - effectiveY);
        int loopGuard = 0;

        while (drawY < viewH && loopGuard < sz * 2) {
            QString fullID = fileList[currentIndex];
            int h = getEstimatedHeight(currentIndex, viewW, viewH);

            QPixmap pix = requestImage(currentIndex, fullID, viewW, viewH);

            if (!pix.isNull()) {
                int xPos = (viewW - pix.width()) / 2;
                if (blurEnabled) {
                    // Apply quick blur via scaled-down-then-up
                    QPixmap blurred = pix.scaled(pix.size() / 8, Qt::KeepAspectRatio, Qt::FastTransformation);
                    blurred = blurred.scaled(pix.size(), Qt::KeepAspectRatio, Qt::FastTransformation);
                    painter.drawPixmap(xPos, drawY, blurred);
                } else {
                    painter.drawPixmap(xPos, drawY, pix);
                }
            } else {
                painter.fillRect(QRect(0, drawY, viewW, h), QColor(30, 30, 30));
                painter.setPen(Qt::gray);
                painter.drawText(QRect(0, drawY, viewW, h), Qt::AlignCenter, "Loading...");
            }

            drawY += h;
            currentIndex = (currentIndex + 1) % sz;
            loopGuard++;
        }
    }

private:
    QMap<QString, ImageVault*> *activeVaults = nullptr;
    std::vector<QString> fileList;
    qint64 scrollY = 0;

    bool fitScreen = false;
    bool snapToGrid = false;
    bool blurEnabled = false;
    bool randomSlideshow = false;
    int currentRenderIndex = 0;
    double zoomFactor = 1.0;

    QCache<int, QPixmap> imageCache{CACHE_SIZE};
    QMap<int, int> imageHeights;
    QSet<int> pendingRequests;
    QTimer* checkTimer;
    QTimer* slideTimer;
    std::mt19937 *randomEngine = new std::mt19937(std::random_device{}());

    void jumpToIndex(int direction) {
        if (fileList.empty()) return;
        int sz = static_cast<int>(fileList.size());

        int targetIdx;
        if (randomSlideshow) {
            std::uniform_int_distribution<int> dist(0, sz - 1);
            targetIdx = dist(*randomEngine);
        } else {
            targetIdx = currentRenderIndex + direction;
            targetIdx = ((targetIdx % sz) + sz) % sz;
        }

        int viewW = width();
        int viewH = height();

        qint64 targetY = 0;
        for (int i = 0; i < targetIdx; i++)
            targetY += getEstimatedHeight(i, viewW, viewH);

        qint64 totalCycleH = 0;
        for (int i = 0; i < sz; i++) totalCycleH += getEstimatedHeight(i, viewW, viewH);
        if (totalCycleH > 0) {
            qint64 loopCount = scrollY / totalCycleH;
            scrollY = (loopCount * totalCycleH) + targetY;
        }

        currentRenderIndex = targetIdx;
        update();
        emit jumpedToIndex(targetIdx);
    }

    int getEstimatedHeight(int index, int w, int screenH) {
        if (imageHeights.contains(index)) return imageHeights[index];
        if (fitScreen) return static_cast<int>(screenH * zoomFactor);
        return static_cast<int>(w * 1.4 * zoomFactor);
    }

    QPixmap requestImage(int index, const QString& fullID, int reqW, int reqH) {
        if (imageCache.contains(index)) return *imageCache.object(index);

        if (!pendingRequests.contains(index)) {
            pendingRequests.insert(index);

            QStringList parts = fullID.split("||");
            if (parts.size() < 2) return QPixmap();
            QString vPath = parts[0];
            std::string fName = parts[1].toStdString();

            (void)QtConcurrent::run([this, index, vPath, fName, reqW, reqH]() {
                if (!activeVaults || !activeVaults->contains(vPath)) return;

                ImageVault* v = (*activeVaults)[vPath];
                std::vector<char> data = v->get_file_data(fName);
                if (data.empty()) return;

                QImage img;
                if (img.loadFromData((const uchar*)data.data(), data.size())) {
                    int finalW = img.width();
                    int finalH = img.height();
                    double aspect = (double)finalH / finalW;

                    if (fitScreen) {
                        finalH = reqH;
                        finalW = static_cast<int>(finalH / aspect);
                        if (finalW > reqW) {
                            finalW = reqW;
                            finalH = static_cast<int>(finalW * aspect);
                        }
                    } else {
                        if (finalW > reqW || finalW < reqW) {
                            finalW = reqW;
                            finalH = static_cast<int>(finalW * aspect);
                        }
                    }

                    finalW = static_cast<int>(finalW * zoomFactor);
                    finalH = static_cast<int>(finalH * zoomFactor);

                    img = img.scaled(finalW, finalH, Qt::KeepAspectRatio, Qt::SmoothTransformation);

                    QMetaObject::invokeMethod(this, [this, index, img, finalH]() {
                        imageCache.insert(index, new QPixmap(QPixmap::fromImage(img)));
                        imageHeights[index] = finalH;
                        pendingRequests.remove(index);
                        update();
                    });
                }
            });
        }
        return QPixmap();
    }
};

#endif
