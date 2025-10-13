// Map for attendance method (VERIFY field - verification method)
// 0=password, 1=fingerprint, 2=face, 3=card, 4=combined
export const ATTENDANCE_METHOD_MAP: { [key: number]: string } = {
  0: "Mật khẩu",
  1: "Vân tay",
  2: "Khuôn mặt",
  3: "Thẻ",
  4: "Kết hợp",
  15: "Khuôn mặt",
};

// Map for punch action (what the 'punch' field represents)
export const PUNCH_ACTION_MAP: { [key: number]: string } = {
  0: "Vào ca",
  1: "Ra ca",
  2: "Nghỉ giải lao",
  3: "Tạm dừng",
  4: "Bắt đầu tăng ca",
  5: "Kết thúc tăng ca",
};
