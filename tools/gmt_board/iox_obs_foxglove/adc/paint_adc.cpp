#include "gf_foxglove/paint_adc.hpp"

namespace gf_foxglove {

extern thread_local int g_bev_sku_override;

std::string paint_adc_bev(const LiveBevState& st, int width, int height) {
  const int prev = g_bev_sku_override;
  g_bev_sku_override = 1;
  std::string png = render_ego_bev_png(st, width, height);
  g_bev_sku_override = prev;
  return png;
}

}  // namespace gf_foxglove
