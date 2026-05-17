#ifndef IMAGE_VAULT_HPP
#define IMAGE_VAULT_HPP

#include <QString>
#include <QFile>
#include <QDir>
#include <QMap>
#include <QByteArray>
#include <QDataStream>
#include <QDebug>
#include <QCryptographicHash>
#include <QSet>
#include <functional>

class ImageVault {
private:
    const char XOR_KEY = 0x5A;
    const char* MAGIC_HEADER = "IROLL_V1";

    struct FileEntry {
        QString filename;
        qint64 offset;
        qint64 compressed_size;
        qint64 original_size;
    };

    QMap<QString, FileEntry> file_index;
    QString archive_path;
    QString last_error;

    void xor_data(QByteArray &buffer) {
        char *data = buffer.data();
        for (int i = 0; i < buffer.size(); ++i) {
            data[i] ^= XOR_KEY;
        }
    }

public:
    void pack(const QString& source_folder, const QString& output_file,
              std::function<void(int, int)> onProgress = nullptr,
              bool skipDuplicates = false)
    {
        QFile out(output_file);
        if (!out.open(QIODevice::WriteOnly)) {
            throw std::runtime_error("Cannot create output file.");
        }

        QDataStream stream(&out);
        stream.writeRawData(MAGIC_HEADER, 8);

        QDir dir(source_folder);
        QStringList filters;
        filters << "*.jpg" << "*.jpeg" << "*.png" << "*.webp" << "*.bmp" << "*.gif";
        QFileInfoList files = dir.entryInfoList(filters, QDir::Files);

        // Dedup by hash if requested
        QSet<QByteArray> seenHashes;
        QFileInfoList uniqueFiles;
        for (const QFileInfo &fi : files) {
            if (skipDuplicates) {
                QFile f(fi.absoluteFilePath());
                if (f.open(QIODevice::ReadOnly)) {
                    QByteArray hash = QCryptographicHash::hash(f.readAll(), QCryptographicHash::Md5);
                    f.close();
                    if (seenHashes.contains(hash)) continue;
                    seenHashes.insert(hash);
                }
            }
            uniqueFiles.append(fi);
        }

        quint32 count = uniqueFiles.size();
        stream << count;

        int processed = 0;
        for (const QFileInfo &fileInfo : uniqueFiles) {
            if (onProgress) onProgress(processed, count);

            QFile inFile(fileInfo.absoluteFilePath());
            if (!inFile.open(QIODevice::ReadOnly)) continue;

            QByteArray rawData = inFile.readAll();
            QByteArray compressedData = qCompress(rawData, -1);
            xor_data(compressedData);

            stream << fileInfo.fileName();
            stream << (qint64)rawData.size();
            stream << (qint64)compressedData.size();
            stream.writeRawData(compressedData.constData(), compressedData.size());

            processed++;
        }

        if (onProgress) onProgress(count, count);
        out.close();
    }

    // Batch: pack each subfolder into its own .iroll in the output directory
    static void packSubfolders(const QString& parent_folder, const QString& output_dir,
                               std::function<void(int, int)> onProgress = nullptr,
                               bool skipDuplicates = false)
    {
        QDir parent(parent_folder);
        QStringList subdirs = parent.entryList(QDir::Dirs | QDir::NoDotAndDotDot);

        int total = subdirs.size();
        for (int i = 0; i < total; ++i) {
            const QString &sub = subdirs[i];
            if (onProgress) onProgress(i, total);

            QString subPath = parent.absoluteFilePath(sub);
            QString outPath = QDir(output_dir).absoluteFilePath(sub + ".iroll");

            ImageVault v;
            v.pack(subPath, outPath, nullptr, skipDuplicates);
        }
        if (onProgress) onProgress(total, total);
    }

    bool load_archive(const QString& path, QString *errorOut = nullptr) {
        archive_path = path;
        file_index.clear();
        last_error.clear();

        QFile in(path);
        if (!in.open(QIODevice::ReadOnly)) {
            last_error = "Cannot open file: " + path;
            if (errorOut) *errorOut = last_error;
            return false;
        }

        QDataStream stream(&in);
        char header[9];
        if (in.read(header, 8) != 8) {
            last_error = "File too small to be a valid iRoll archive";
            if (errorOut) *errorOut = last_error;
            return false;
        }
        header[8] = '\0';
        if (strcmp(header, MAGIC_HEADER) != 0) {
            last_error = "Invalid magic header (not an iRoll archive)";
            if (errorOut) *errorOut = last_error;
            return false;
        }

        quint32 count;
        stream >> count;

        for (quint32 i = 0; i < count; ++i) {
            QString name;
            qint64 original_size, compressed_size;
            stream >> name >> original_size >> compressed_size;
            qint64 offset = in.pos();
            file_index[name] = {name, offset, compressed_size, original_size};
            if (!in.seek(offset + compressed_size)) {
                last_error = "Corrupt archive: cannot seek to next entry";
                if (errorOut) *errorOut = last_error;
                return false;
            }
        }
        return true;
    }

    QString get_last_error() const { return last_error; }

    std::vector<std::string> get_file_list() {
        std::vector<std::string> names;
        for (auto key : file_index.keys()) names.push_back(key.toStdString());
        return names;
    }

    qint64 get_file_original_size(const std::string& filename_std) const {
        QString filename = QString::fromStdString(filename_std);
        if (file_index.contains(filename))
            return file_index[filename].original_size;
        return -1;
    }

    std::vector<char> get_file_data(const std::string& filename_std) {
        QString filename = QString::fromStdString(filename_std);
        if (!file_index.contains(filename)) return {};

        FileEntry entry = file_index[filename];
        QFile in(archive_path);
        if (!in.open(QIODevice::ReadOnly)) return {};
        if (!in.seek(entry.offset)) return {};

        QByteArray data = in.read(entry.compressed_size);
        xor_data(data);
        QByteArray decompressed = qUncompress(data);
        return std::vector<char>(decompressed.begin(), decompressed.end());
    }

    bool extract_file(const std::string& filename_std, const QString& output_path) {
        QString filename = QString::fromStdString(filename_std);
        if (!file_index.contains(filename)) {
            last_error = "File not found in archive: " + filename;
            return false;
        }

        FileEntry entry = file_index[filename];
        QFile in(archive_path);
        if (!in.open(QIODevice::ReadOnly)) {
            last_error = "Cannot open archive for reading";
            return false;
        }
        if (!in.seek(entry.offset)) {
            last_error = "Cannot seek to file entry";
            return false;
        }

        QByteArray data = in.read(entry.compressed_size);
        xor_data(data);
        QByteArray decompressed = qUncompress(data);

        QFile out(output_path);
        if (!out.open(QIODevice::WriteOnly)) {
            last_error = "Cannot write to: " + output_path;
            return false;
        }
        out.write(decompressed);
        out.close();
        return true;
    }

    int extract_all(const QString& output_dir,
                    std::function<void(int, int)> onProgress = nullptr) {
        QDir dir(output_dir);
        if (!dir.exists()) dir.mkpath(".");

        QStringList keys = file_index.keys();
        int total = keys.size();
        int success = 0;

        for (int i = 0; i < total; ++i) {
            if (onProgress) onProgress(i, total);
            QString fname = keys[i];
            QString outPath = dir.absoluteFilePath(fname);
            if (extract_file(fname.toStdString(), outPath))
                success++;
        }
        if (onProgress) onProgress(total, total);
        return success;
    }
};

#endif
