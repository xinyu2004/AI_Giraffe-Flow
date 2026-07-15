#include "gf_ara/com/binding/cross_domain_ipc/transport.hpp"

#include "io_types.hpp"

#include <cstdlib>
#include <iostream>
#include <string>

namespace {

const char* SockPath() {
  const char* p = std::getenv("GF_CP_IPC_PATH");
  return p && p[0] ? p : gf_ara::com::binding::cross_domain_ipc::kDefaultSockPath;
}

int ExpectRounds() {
  const char* e = std::getenv("GF_MCU_PEER_ROUNDS");
  if (e && e[0]) {
    return std::atoi(e);
  }
  return 5;
}

}  // namespace

int main() {
  using namespace gf_ara::com::binding::cross_domain_ipc;
  using namespace gf::demo::mcu_cp_gateway;

  const int expect = ExpectRounds();
  const std::string path = SockPath();
  std::cout << "gf-cp-ipc-peer: listening on " << path
            << " (expect " << expect << " TrajPlot)\n";

  SocketTransport peer;
  if (!peer.ListenAndAccept(path)) {
    return 1;
  }
  std::cout << "gf-cp-ipc-peer: gateway connected\n";

  for (int seq = 0; seq < expect; ++seq) {
    IPC_CanInfo_20ms_St can20{};
    can20.fVehicleSpeed = 1.0f + 0.1f * static_cast<float>(seq % 20);
    can20.fYawRate = 0.05f;
    can20.fLeftFrontWheelSpeed = can20.fVehicleSpeed;
    can20.fRightFrontWheelSpeed = can20.fVehicleSpeed;
    can20.fLeftRearWheelSpeed = can20.fVehicleSpeed;
    can20.fRightRearWheelSpeed = can20.fVehicleSpeed;
    if (!SendPod(peer, MsgType::CanInfo20ms, can20)) {
      std::cerr << "gf-cp-ipc-peer: send CanInfo20ms failed\n";
      return 1;
    }

    IPC_CanInfo_10ms_St can10{};
    can10.fSteerAngle = 2.0f;
    can10.ucGear = 4;
    can10.uiSyncX = 10.0f + static_cast<float>(seq);
    can10.uiSyncY = 20.0f;
    can10.uiSyncAngle = 0.2f;
    if (!SendPod(peer, MsgType::CanInfo10ms, can10)) {
      std::cerr << "gf-cp-ipc-peer: send CanInfo10ms failed\n";
      return 1;
    }

    IPC_CanInfo_100ms_St can100{};
    can100.uiAPAOnOff = 1;
    can100.uiAPAMode = 2;
    can100.uiAPAStatus = 1;
    if (!SendPod(peer, MsgType::CanInfo100ms, can100)) {
      std::cerr << "gf-cp-ipc-peer: send CanInfo100ms failed\n";
      return 1;
    }
    std::cout << "gf-cp-ipc-peer: sent CanInfo seq=" << seq << std::endl;

    // Expect TrajPlot then PParking (gateway lockstep)
    IPC_TrajPlot_St traj{};
    if (!RecvPod(peer, MsgType::TrajPlot, &traj)) {
      std::cerr << "gf-cp-ipc-peer: TrajPlot recv failed\n";
      return 1;
    }
    std::cout << "gf-cp-ipc-peer: got TrajPlot points="
              << static_cast<int>(traj.PointLength) << " (" << (seq + 1) << "/"
              << expect << ")\n";

    IPC_P_Parking_St cmd{};
    if (!RecvPod(peer, MsgType::PParking, &cmd)) {
      std::cerr << "gf-cp-ipc-peer: P_Parking recv failed\n";
      return 1;
    }
    std::cout << "gf-cp-ipc-peer: got P_Parking steer="
              << cmd.PACtl_StrCtl_angCmdEPS_avm << "\n";
  }

  std::cout << "gf-cp-ipc-peer: OK\n";
  return 0;
}
