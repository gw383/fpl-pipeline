def news_card(row):

    text = row["news"].lower()

    if "injury" in text:
        colour = "#d9534f"
    elif "suspended" in text:
        colour = "#f0ad4e"
    elif "available" in text:
        colour = "#5cb85c"
    else:
        colour = "#428bca"

    return f"""
    <div style="
        background:white;
        border-left:5px solid {colour};
        border-radius:8px;
        padding:8px 10px;
        margin-bottom:5px;
        box-shadow:0 1px 3px rgba(0,0,0,0.08);
    ">

        <div style="font-weight:700;">
            {row['player']}
        </div>

        <div style="font-size:12px;">
            {row['news']}
        </div>

        <div style="font-size:10px;color:#777;">
            {row['date']}
        </div>

    </div>
    """
