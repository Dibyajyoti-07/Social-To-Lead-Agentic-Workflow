def mock_lead_capture(name: str, email: str, platform: str) -> str:
    """
    Mock tool to simulate capturing a lead.
    Only call this when all three fields are non-empty.
    """
    print(f"\n✅ Lead captured successfully: {name} | {email} | {platform}\n")
    return f"Lead captured: {name} | {email} | {platform}"

