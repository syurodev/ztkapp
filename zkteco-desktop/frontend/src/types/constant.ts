// Map for attendance method (what the 'status' field represents)
export const ATTENDANCE_METHOD_MAP: { [key: number]: string } = {
  1: "Fingerprint",
  4: "Card",
};

// Map for punch action (what the 'punch' field represents)
export const PUNCH_ACTION_MAP: { [key: number]: string } = {
  0: "Check-in",
  1: "Check-out",
  2: "Break",
  3: "Interrupt",
  4: "Overtime Start",
  5: "Overtime End",
};
