/** 产品引导状态：记录用户是否已经看过新版终端引导。 */

export const PRODUCT_TOUR_STORAGE_KEY = "financial-agent-product-tour-v1";

/** 判断当前浏览器是否已经完成引导。 */
export function hasCompletedProductTour() {
  if (typeof window === "undefined") return true;
  return window.localStorage.getItem(PRODUCT_TOUR_STORAGE_KEY) === "done";
}

/** 标记当前浏览器已经完成或跳过引导。 */
export function writeProductTourCompleted() {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(PRODUCT_TOUR_STORAGE_KEY, "done");
}
