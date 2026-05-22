import { NextResponse } from "next/server";

export async function POST() {
  const response = NextResponse.json({ message: "Sesión cerrada" });
  response.cookies.delete("taxops_refresh");
  return response;
}
