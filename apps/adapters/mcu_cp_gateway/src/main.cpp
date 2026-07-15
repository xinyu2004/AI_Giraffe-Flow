#include "gf_ara/com/binding/cross_domain_ipc/transport.hpp"

#include "io_types.hpp"

#include <chrono>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <thread>

namespace {

const char* SockPath() {
  const char* p = std::getenv("GF_CP_IPC_PATH");
  return p && p[0] ? p : gf_ara::com::binding::cross_domain_ipc::kDefaultSockPath;
}

int ExpectRounds() {
  const char* e = std::getenv("GF_MCU_GATEWAY_ROUNDS");
  if (e && e[0]) {
    return std::atoi(e);
  }
  const char* p = std::getenv("GF_MCU_PEER_ROUNDS");
  if (p && p[0]) {
    return std::atoi(p);
  }
  return 5;
}

gf::demo::mcu_cp_gateway::EgoMotion MapEgo(
    const gf::demo::mcu_cp_gateway::IPC_CanInfo_20ms_St& c20,
    const gf::demo::mcu_cp_gateway::IPC_CanInfo_10ms_St& c10) {
  gf::demo::mcu_cp_gateway::EgoMotion ego{};
  ego.timestamp_ns = static_cast<uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(
          std::chrono::steady_clock::now().time_since_epoch())
          .count());
  ego.speed_mps = c20.fVehicleSpeed;
  ego.yaw_rate_degps = c20.fYawRate;
  ego.steer_angle_deg = c10.fSteerAngle;
  ego.gear = c10.ucGear;
  ego.wheel_speed_fl_mps = c20.fLeftFrontWheelSpeed;
  ego.wheel_speed_fr_mps = c20.fRightFrontWheelSpeed;
  ego.wheel_speed_rl_mps = c20.fLeftRearWheelSpeed;
  ego.wheel_speed_rr_mps = c20.fRightRearWheelSpeed;
  return ego;
}

gf::demo::mcu_cp_gateway::IPC_TrajPlot_St MakeTraj(int seq) {
  gf::demo::mcu_cp_gateway::IPC_TrajPlot_St t{};
  t.PointLength = 4;
  for (uint8_t i = 0; i < t.PointLength; ++i) {
    t.PointX[i] = static_cast<float>(seq) + 0.5f * static_cast<float>(i);
    t.PointY[i] = 0.1f * static_cast<float>(i);
  }
  t.GearShiftPointFst = 1;
  t.GearShiftPointScd = 2;
  return t;
}

gf::demo::mcu_cp_gateway::IPC_P_Parking_St MakeParking(int seq) {
  gf::demo::mcu_cp_gateway::IPC_P_Parking_St p{};
  p.PACtl_StrCtl_angCmdEPS_avm = 1.5 + 0.01 * seq;
  p.PACtl_LngCtl_lVehDisDes_avm = 0.5;
  p.PACtl_ProMng_numGearDes_avm = 4.0;
  p.PACtl_LngCtl_stEbrkExt_avm = 0.0;
  return p;
}

}  // namespace

int main() {
  using namespace gf_ara::com::binding::cross_domain_ipc;
  using namespace gf::demo::mcu_cp_gateway;

  const int expect = ExpectRounds();
  const std::string path = SockPath();
  std::cout << "gf-mcu-cp-gateway: connecting to " << path
            << " (rounds=" << expect << ")\n";

  SocketTransport gw;
  bool connected = false;
  for (int i = 0; i < 100; ++i) {
    if (gw.Connect(path)) {
      connected = true;
      break;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
  }
  if (!connected) {
    std::cerr << "gf-mcu-cp-gateway: connect failed\n";
    return 1;
  }
  std::cout << "gf-mcu-cp-gateway: connected\n";

  for (int seq = 0; seq < expect; ++seq) {
    IPC_CanInfo_20ms_St can20{};
    IPC_CanInfo_10ms_St can10{};
    IPC_CanInfo_100ms_St can100{};
    bool got20 = false;
    bool got10 = false;
    bool got100 = false;

    // Drain one lockstep burst from peer
    while (!(got20 && got10 && got100)) {
      MsgType type{};
      alignas(8) uint8_t buf[256]{};
      uint32_t n = 0;
      if (!gw.Recv(&type, buf, sizeof(buf), &n)) {
        std::cerr << "gf-mcu-cp-gateway: recv failed\n";
        return 1;
      }
      if (type == MsgType::CanInfo20ms && n == sizeof(can20)) {
        std::memcpy(&can20, buf, sizeof(can20));
        got20 = true;
      } else if (type == MsgType::CanInfo10ms && n == sizeof(can10)) {
        std::memcpy(&can10, buf, sizeof(can10));
        got10 = true;
      } else if (type == MsgType::CanInfo100ms && n == sizeof(can100)) {
        std::memcpy(&can100, buf, sizeof(can100));
        got100 = true;
      }
    }

    const EgoMotion ego = MapEgo(can20, can10);
    std::cout << "gf-mcu-cp-gateway: EgoMotion speed=" << ego.speed_mps
              << " steer=" << ego.steer_angle_deg
              << " apa=" << static_cast<int>(can100.uiAPAOnOff) << " seq=" << seq
              << std::endl;

    // AP → MCU (would come from planning via iceoryx in full SKU)
    const auto traj = MakeTraj(seq);
    const auto park = MakeParking(seq);
    if (!SendPod(gw, MsgType::TrajPlot, traj)) {
      std::cerr << "gf-mcu-cp-gateway: send TrajPlot failed\n";
      return 1;
    }
    if (!SendPod(gw, MsgType::PParking, park)) {
      std::cerr << "gf-mcu-cp-gateway: send P_Parking failed\n";
      return 1;
    }
    std::cout << "gf-mcu-cp-gateway: sent TrajPlot+P_Parking seq=" << seq
              << std::endl;
  }

  std::cout << "gf-mcu-cp-gateway: OK\n";
  return 0;
}
