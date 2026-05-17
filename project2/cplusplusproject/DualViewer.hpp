// DualViewer.hpp
#ifndef DUAL_VIEWER_HPP
#define DUAL_VIEWER_HPP

#include <QWidget>
#include <QHBoxLayout>
#include "InfiniteViewer.hpp"

class DualPaneWidget : public QWidget {
    Q_OBJECT
public:
    explicit DualPaneWidget(QWidget *parent = nullptr) : QWidget(parent) {
        QHBoxLayout *layout = new QHBoxLayout(this);
        layout->setContentsMargins(0, 0, 0, 0);
        layout->setSpacing(0);

        leftViewer = new InfiniteScrollWidget();
        rightViewer = new InfiniteScrollWidget();

        layout->addWidget(leftViewer);
        layout->addWidget(rightViewer);

        // Synchronise scrolling (with guard against feedback loops)
        connect(leftViewer, &InfiniteScrollWidget::scrolled,
                this, &DualPaneWidget::syncScrollLeftToRight);
        connect(rightViewer, &InfiniteScrollWidget::scrolled,
                this, &DualPaneWidget::syncScrollRightToLeft);

        // Synchronise jumps (snap to grid, click in gallery, etc.)
        connect(leftViewer, &InfiniteScrollWidget::jumpedToIndex,
                this, &DualPaneWidget::syncJumpLeftToRight);
        connect(rightViewer, &InfiniteScrollWidget::jumpedToIndex,
                this, &DualPaneWidget::syncJumpRightToLeft);

        // Forward user navigation signals to stop slideshow
        connect(leftViewer, &InfiniteScrollWidget::userNavigated,
                this, &DualPaneWidget::userNavigated);
        connect(rightViewer, &InfiniteScrollWidget::userNavigated,
                this, &DualPaneWidget::userNavigated);
    }

    void setVaults(QMap<QString, ImageVault*> *vMap) {
        leftViewer->setVaults(vMap);
        rightViewer->setVaults(vMap);
    }

    void setLeftImages(const std::vector<QString>& files) {
        leftViewer->loadImages(files);
    }

    void setRightImages(const std::vector<QString>& files) {
        rightViewer->loadImages(files);
    }

    void setFitToScreen(bool enable) {
        leftViewer->setFitToScreen(enable);
        rightViewer->setFitToScreen(enable);
    }

    void setSnapToGrid(bool enable) {
        leftViewer->setSnapToGrid(enable);
        rightViewer->setSnapToGrid(enable);
    }

    void toggleSlideshow(bool active, int interval) {
        leftViewer->toggleSlideshow(active, interval);
        rightViewer->toggleSlideshow(active, interval);
    }

    void updateSlideInterval(int sec) {
        leftViewer->updateSlideInterval(sec);
        rightViewer->updateSlideInterval(sec);
    }

    void stopSlideshow() {
        leftViewer->stopSlideshow();
        rightViewer->stopSlideshow();
    }

    void setZoom(double factor) {
        leftViewer->setZoom(factor);
        rightViewer->setZoom(factor);
    }

    // Jump to a specific image index – left pane jumps, right follows via signal
    void jumpToSpecificIndex(int index) {
        leftViewer->jumpToSpecificIndex(index);
    }

    // Pass focus to left viewer for keyboard events
    void grabFocus() {
        leftViewer->setFocus();
    }

    InfiniteScrollWidget* left() const { return leftViewer; }
    InfiniteScrollWidget* right() const { return rightViewer; }

signals:
    void userNavigated();

private slots:
    void syncScrollLeftToRight(qint64 newY) {
        if (syncGuard) return;
        syncGuard = true;
        rightViewer->blockSignals(true);
        rightViewer->setScrollY(newY);
        rightViewer->blockSignals(false);
        syncGuard = false;
    }

    void syncScrollRightToLeft(qint64 newY) {
        if (syncGuard) return;
        syncGuard = true;
        leftViewer->blockSignals(true);
        leftViewer->setScrollY(newY);
        leftViewer->blockSignals(false);
        syncGuard = false;
    }

    void syncJumpLeftToRight(int index) {
        if (syncGuard) return;
        syncGuard = true;
        rightViewer->blockSignals(true);
        rightViewer->jumpToSpecificIndex(index);
        rightViewer->blockSignals(false);
        syncGuard = false;
    }

    void syncJumpRightToLeft(int index) {
        if (syncGuard) return;
        syncGuard = true;
        leftViewer->blockSignals(true);
        leftViewer->jumpToSpecificIndex(index);
        leftViewer->blockSignals(false);
        syncGuard = false;
    }

private:
    InfiniteScrollWidget *leftViewer;
    InfiniteScrollWidget *rightViewer;
    bool syncGuard = false;
};

#endif
