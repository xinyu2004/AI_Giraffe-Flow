#include "gf_ara/com/binding/dds/cyclone_transport.hpp"

#if defined(GF_DDS_USE_CYCLONEDDS) && GF_DDS_USE_CYCLONEDDS

#include "GfBlob.h"

#include "dds/dds.h"

#include <cctype>
#include <cstring>
#include <iostream>
#include <mutex>
#include <string>
#include <utility>

namespace gf_ara::com::binding::dds {
namespace {

std::mutex g_mu;
dds_entity_t g_participant{0};
std::string g_name;

std::string TopicName(const ServicePath& path) {
  // DDS topic names: avoid raw '/'
  std::string t = path.service + "__" + path.instance + "__" + path.event;
  for (char& c : t) {
    if (!(std::isalnum(static_cast<unsigned char>(c)) || c == '_' || c == '-')) {
      c = '_';
    }
  }
  return t;
}

}  // namespace

void CycloneEnsureParticipant(const std::string& name) {
  std::lock_guard<std::mutex> lock(g_mu);
  if (g_participant > 0) {
    return;
  }
  g_name = name;
  g_participant = dds_create_participant(DDS_DOMAIN_DEFAULT, nullptr, nullptr);
  if (g_participant < 0) {
    std::cerr << "gf_ara::dds: dds_create_participant failed: "
              << dds_strretcode(-g_participant) << "\n";
    g_participant = 0;
  }
}

static dds_entity_t Participant() {
  std::lock_guard<std::mutex> lock(g_mu);
  return g_participant;
}

CycloneWriter::CycloneWriter(const ServicePath& path) {
  const dds_entity_t participant = Participant();
  if (participant <= 0) {
    return;
  }
  const std::string topic_name = TopicName(path);
  topic_ = dds_create_topic(participant, &gf_Blob_desc, topic_name.c_str(), nullptr, nullptr);
  if (topic_ < 0) {
    std::cerr << "gf_ara::dds: dds_create_topic(writer) failed: " << dds_strretcode(-topic_)
              << "\n";
    topic_ = 0;
    return;
  }
  dds_qos_t* qos = dds_create_qos();
  dds_qset_reliability(qos, DDS_RELIABILITY_RELIABLE, DDS_MSECS(100));
  writer_ = dds_create_writer(participant, topic_, qos, nullptr);
  dds_delete_qos(qos);
  if (writer_ < 0) {
    std::cerr << "gf_ara::dds: dds_create_writer failed: " << dds_strretcode(-writer_) << "\n";
    writer_ = 0;
  }
}

CycloneWriter::CycloneWriter(CycloneWriter&& other) noexcept
    : topic_(other.topic_), writer_(other.writer_) {
  other.topic_ = 0;
  other.writer_ = 0;
}

CycloneWriter& CycloneWriter::operator=(CycloneWriter&& other) noexcept {
  if (this != &other) {
    if (writer_ > 0) {
      dds_delete(writer_);
    }
    if (topic_ > 0) {
      dds_delete(topic_);
    }
    topic_ = other.topic_;
    writer_ = other.writer_;
    other.topic_ = 0;
    other.writer_ = 0;
  }
  return *this;
}

CycloneWriter::~CycloneWriter() {
  if (writer_ > 0) {
    dds_delete(writer_);
  }
  if (topic_ > 0) {
    dds_delete(topic_);
  }
}

bool CycloneWriter::Write(const void* data, std::size_t size) {
  if (writer_ <= 0 || data == nullptr || size == 0 || size > sizeof(gf_Blob::bytes)) {
    return false;
  }
  gf_Blob sample{};
  sample.stamp_ns = 0;
  sample.size = static_cast<uint32_t>(size);
  std::memcpy(sample.bytes, data, size);
  const dds_return_t rc = dds_write(writer_, &sample);
  return rc == DDS_RETCODE_OK;
}

CycloneReader::CycloneReader(const ServicePath& path) {
  const dds_entity_t participant = Participant();
  if (participant <= 0) {
    return;
  }
  const std::string topic_name = TopicName(path);
  topic_ = dds_create_topic(participant, &gf_Blob_desc, topic_name.c_str(), nullptr, nullptr);
  if (topic_ < 0) {
    std::cerr << "gf_ara::dds: dds_create_topic(reader) failed: " << dds_strretcode(-topic_)
              << "\n";
    topic_ = 0;
    return;
  }
  dds_qos_t* qos = dds_create_qos();
  dds_qset_reliability(qos, DDS_RELIABILITY_RELIABLE, DDS_MSECS(100));
  reader_ = dds_create_reader(participant, topic_, qos, nullptr);
  dds_delete_qos(qos);
  if (reader_ < 0) {
    std::cerr << "gf_ara::dds: dds_create_reader failed: " << dds_strretcode(-reader_) << "\n";
    reader_ = 0;
  }
}

CycloneReader::CycloneReader(CycloneReader&& other) noexcept
    : topic_(other.topic_), reader_(other.reader_) {
  other.topic_ = 0;
  other.reader_ = 0;
}

CycloneReader& CycloneReader::operator=(CycloneReader&& other) noexcept {
  if (this != &other) {
    if (reader_ > 0) {
      dds_delete(reader_);
    }
    if (topic_ > 0) {
      dds_delete(topic_);
    }
    topic_ = other.topic_;
    reader_ = other.reader_;
    other.topic_ = 0;
    other.reader_ = 0;
  }
  return *this;
}

CycloneReader::~CycloneReader() {
  if (reader_ > 0) {
    dds_delete(reader_);
  }
  if (topic_ > 0) {
    dds_delete(topic_);
  }
}

bool CycloneReader::Take(void* out, std::size_t size) {
  if (reader_ <= 0 || out == nullptr || size == 0) {
    return false;
  }
  void* samples[1] = {nullptr};
  dds_sample_info_t infos[1];
  const dds_return_t n = dds_take(reader_, samples, infos, 1, 1);
  if (n <= 0) {
    return false;
  }
  bool ok = false;
  if (infos[0].valid_data && samples[0] != nullptr) {
    const auto* blob = static_cast<const gf_Blob*>(samples[0]);
    if (blob->size == size && blob->size <= sizeof(blob->bytes)) {
      std::memcpy(out, blob->bytes, size);
      ok = true;
    }
  }
  dds_return_loan(reader_, samples, n);
  return ok;
}

}  // namespace gf_ara::com::binding::dds

#endif  // GF_DDS_USE_CYCLONEDDS
