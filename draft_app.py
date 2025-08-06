"""
FPL Draft Assistant App
========================

This script implements a simple web application using `streamlit` to assist a user
during a Fantasy Premier League (FPL) draft.  It leverages the provided
``Player_Data_CSV.csv`` file to display a sortable, filterable list of players
alongside key metrics such as goals, assists, clean sheets and a weighted
performance score.  The app allows the user to build and manage two
collections:

* **My Team** – the 15 players the user has drafted (2 Goalkeepers, 5
  Defenders, 5 Midfielders and 3 Forwards).  These constraints are enforced
  automatically.
* **Wish List** – players the user would like to pick if they remain available.

The user can also mark players as **taken by other managers**; once a player
is taken they are removed from all views and from the wish list or team if
present.  At a glance, the app shows how many players have been drafted in each
position and offers suggestions for remaining slots based on the weighted
performance score.

To run this application:

1. Install the dependencies (only needed once):

   ```shell
   pip install streamlit pandas
   ```

2. Launch the app using Streamlit:

   ```shell
   streamlit run draft_app.py
   ```

The interface will open in your default web browser.  When the FPL draft is
underway you can quickly search for players, add them to your wish list or
team, and mark others as taken.  The app automatically updates all lists so
that you can make informed decisions even in a fast‑paced draft.
"""

import pandas as pd
import streamlit as st
from typing import List


@st.cache_data
def load_data(csv_path: str) -> pd.DataFrame:
    """Load player data from the provided CSV file.

    The data file contains historical statistics for each player along with a
    weighted performance score.  This function renames some columns for
    convenience and calculates additional helper columns if necessary.

    Parameters
    ----------
    csv_path : str
        Path to the ``Player_Data_CSV.csv`` file.

    Returns
    -------
    pandas.DataFrame
        DataFrame containing player data.
    """
    df = pd.read_csv(csv_path)

    # Rename columns for easier referencing
    rename_map = {
        'Player Name': 'Player',
        'Performance Score (Weighted)': 'Weighted Score',
        'Total Points 2025/26': 'Points 25/26',
        'Goals 2025/26': 'Goals 25/26',
        'Assists 2025/26': 'Assists 25/26',
        'Clean Sheets 2025/26': 'CS 25/26',
        'Minutes 2025/26': 'Minutes 25/26',
        'Total Points 2024/25': 'Points 24/25',
        'Goals 2024/25': 'Goals 24/25',
        'Assists 2024/25': 'Assists 24/25',
        'Clean Sheets 2024/25': 'CS 24/25',
        'Minutes 2024/25': 'Minutes 24/25',
        'Total Points 2023/24': 'Points 23/24',
        'Goals 2023/24': 'Goals 23/24',
        'Assists 2023/24': 'Assists 23/24',
        'Clean Sheets 2023/24': 'CS 23/24',
        'Minutes 2023/24': 'Minutes 23/24',
        'Price 2025/26': 'Price',
        'Performance Score 2025/26': 'Score 25/26',
        'Performance Score 2024/25': 'Score 24/25',
        'Performance Score 2023/24': 'Score 23/24',
    }
    df = df.rename(columns=rename_map)

    # Coerce numeric columns where possible
    numeric_cols = [
        'Weighted Score', 'Points 25/26', 'Goals 25/26', 'Assists 25/26', 'CS 25/26', 'Minutes 25/26',
        'Points 24/25', 'Goals 24/25', 'Assists 24/25', 'CS 24/25', 'Minutes 24/25',
        'Points 23/24', 'Goals 23/24', 'Assists 23/24', 'CS 23/24', 'Minutes 23/24',
        'Price', 'Score 25/26', 'Score 24/25', 'Score 23/24'
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def initialise_session_state():
    """Initialise persistent session state variables.

    Streamlit's session state allows us to remember user selections across
    reruns.  This function ensures that the keys for the wish list, my team
    and taken players are present and initialised.
    """
    if 'wish_list' not in st.session_state:
        st.session_state.wish_list: List[str] = []
    if 'my_team' not in st.session_state:
        st.session_state.my_team: List[str] = []
    if 'taken_players' not in st.session_state:
        st.session_state.taken_players: List[str] = []


def filter_and_sort_players(df: pd.DataFrame,
                            available_only: bool = True,
                            positions: List[str] = None,
                            search: str = "",
                            sort_by: str = 'Weighted Score',
                            ascending: bool = False) -> pd.DataFrame:
    """Filter and sort the players DataFrame based on user selections.

    Parameters
    ----------
    df : pandas.DataFrame
        The full player DataFrame.
    available_only : bool, default True
        If True, exclude players already taken by other managers.
    positions : list of str or None
        List of positions to include.  If None, include all positions.
    search : str
        Text search to filter player names.
    sort_by : str
        Column to sort by.
    ascending : bool
        Sort order.  False means descending (best first).

    Returns
    -------
    pandas.DataFrame
        Filtered and sorted DataFrame.
    """
    result = df.copy()

    # Exclude taken players if requested
    if available_only and len(st.session_state.taken_players) > 0:
        result = result[~result['Player'].isin(st.session_state.taken_players)]

    # Filter by positions
    if positions:
        result = result[result['Position'].isin(positions)]

    # Apply search filter
    if search:
        result = result[result['Player'].str.contains(search, case=False, na=False)]

    # Sort
    if sort_by in result.columns:
        result = result.sort_values(by=sort_by, ascending=ascending)

    return result


def count_positions(players: List[str], df: pd.DataFrame) -> dict:
    """Count the number of selected players by position.

    Parameters
    ----------
    players : list of str
        List of player names to count.
    df : pandas.DataFrame
        DataFrame containing player information.

    Returns
    -------
    dict
        Dictionary mapping each position to the count of players in that position.
    """
    pos_counts = {'GK': 0, 'DEF': 0, 'MID': 0, 'FWD': 0}
    if players:
        subset = df[df['Player'].isin(players)]
        for pos, group in subset.groupby('Position'):
            pos_counts[pos] = len(group)
    return pos_counts


def remaining_slots(pos_counts: dict) -> dict:
    """Calculate remaining slots in each position for the team.

    The FPL draft format requires: 2 Goalkeepers, 5 Defenders, 5 Midfielders
    and 3 Forwards (total 15 players).  This function calculates how many
    slots remain in each position given the current counts.

    Parameters
    ----------
    pos_counts : dict
        Current counts of players per position.

    Returns
    -------
    dict
        Remaining number of slots per position.
    """
    max_slots = {'GK': 2, 'DEF': 5, 'MID': 5, 'FWD': 3}
    return {pos: max_slots[pos] - pos_counts.get(pos, 0) for pos in max_slots}


def can_add_to_team(player_name: str, df: pd.DataFrame) -> bool:
    """Check whether a player can be added to the team respecting position limits.

    Parameters
    ----------
    player_name : str
        The player to add.
    df : pandas.DataFrame
        DataFrame containing player information.

    Returns
    -------
    bool
        True if the player can be added, False otherwise.
    """
    if player_name in st.session_state.my_team:
        return False  # already in team
    if player_name in st.session_state.taken_players:
        return False  # taken by others

    # Check team size limit (15 players)
    if len(st.session_state.my_team) >= 15:
        return False

    # Check position limits
    pos = df.loc[df['Player'] == player_name, 'Position'].values
    if len(pos) == 0:
        return False
    pos = pos[0]
    pos_counts = count_positions(st.session_state.my_team, df)
    slots_left = remaining_slots(pos_counts)
    return slots_left.get(pos, 0) > 0


def display_team(df: pd.DataFrame):
    """Render the current team and show position counts and suggestions.

    Parameters
    ----------
    df : pandas.DataFrame
        The full player DataFrame.
    """
    st.subheader("My Team")
    pos_counts = count_positions(st.session_state.my_team, df)
    slots_left = remaining_slots(pos_counts)

    # Display counts and remaining slots
    st.write(f"**Total players drafted:** {len(st.session_state.my_team)} / 15")
    cols = st.columns(4)
    positions = ['GK', 'DEF', 'MID', 'FWD']
    for i, pos in enumerate(positions):
        cols[i].metric(f"{pos}", f"{pos_counts[pos]} drafted", f"{slots_left[pos]} left")

    # Show team details
    if st.session_state.my_team:
        team_df = df[df['Player'].isin(st.session_state.my_team)]
        team_df = team_df.sort_values(by='Position')
        st.dataframe(team_df[['Player', 'Team', 'Position', 'Weighted Score', 'Points 25/26', 'Goals 25/26', 'Assists 25/26', 'CS 25/26']], height=300)
    else:
        st.info("No players drafted yet.")

    # Option to remove players from team
    if st.session_state.my_team:
        with st.form("remove_from_team"):
            remove_player = st.multiselect("Remove players from team", options=st.session_state.my_team)
            submitted = st.form_submit_button("Remove Selected")
            if submitted and remove_player:
                for p in remove_player:
                    if p in st.session_state.my_team:
                        st.session_state.my_team.remove(p)
                        # return the player to available pool automatically


def display_wish_list(df: pd.DataFrame):
    """Render the wish list with options to remove players.

    Parameters
    ----------
    df : pandas.DataFrame
        The full player DataFrame.
    """
    st.subheader("Wish List")
    if st.session_state.wish_list:
        wish_df = df[df['Player'].isin(st.session_state.wish_list)].copy()
        wish_df = wish_df.sort_values(by='Weighted Score', ascending=False)
        st.dataframe(wish_df[['Player', 'Team', 'Position', 'Weighted Score', 'Points 25/26', 'Goals 25/26', 'Assists 25/26', 'CS 25/26']], height=300)
    else:
        st.info("Your wish list is empty. Add players you hope to draft soon.")

    # Option to remove players from wish list
    if st.session_state.wish_list:
        with st.form("remove_from_wish"):
            remove_player = st.multiselect("Remove players from wish list", options=st.session_state.wish_list)
            submitted = st.form_submit_button("Remove Selected")
            if submitted and remove_player:
                for p in remove_player:
                    if p in st.session_state.wish_list:
                        st.session_state.wish_list.remove(p)


def display_suggestions(df: pd.DataFrame, slots_left: dict):
    """Suggest top available players for each position where slots remain.

    Parameters
    ----------
    df : pandas.DataFrame
        The full player DataFrame.
    slots_left : dict
        Remaining slots per position.
    """
    st.subheader("Suggestions for Remaining Slots")
    for pos, num_left in slots_left.items():
        if num_left <= 0:
            continue
        # Filter top available players for this position that are not taken and not in team
        available = df[~df['Player'].isin(st.session_state.taken_players + st.session_state.my_team)]
        candidates = available[available['Position'] == pos]
        candidates = candidates.sort_values(by='Weighted Score', ascending=False).head(max(num_left * 2, 5))
        if not candidates.empty:
            st.write(f"**{pos} – need {num_left} more**")
            st.dataframe(candidates[['Player', 'Team', 'Weighted Score', 'Points 25/26', 'Goals 25/26', 'Assists 25/26']], height=200)


def main():
    st.set_page_config(page_title="FPL Draft Assistant", layout="wide")
    st.title("FPL Draft Assistant")
    st.write(
        "This tool helps you manage your team and wish list during a Fantasy Premier League draft. "
        "Select players to add them to your wish list or team, mark players taken by others, and get quick suggestions for remaining slots."
    )

    # Load data and initialise session state
    df = load_data('../../Desktop/Player_Data_CSV.csv')
    initialise_session_state()

    # Sidebar controls
    st.sidebar.header("Filters & Sorting")
    # Position filter
    all_positions = ['GK', 'DEF', 'MID', 'FWD']
    selected_positions = st.sidebar.multiselect("Positions to show", options=all_positions, default=all_positions)
    # Sort options
    sort_options = ['Weighted Score', 'Points 25/26', 'Goals 25/26', 'Assists 25/26', 'CS 25/26', 'Price']
    sort_by = st.sidebar.selectbox("Sort by", options=sort_options, index=0)
    ascending = st.sidebar.checkbox("Ascending order", value=False)
    search_term = st.sidebar.text_input("Search player name")

    # Filter and sort players
    filtered_df = filter_and_sort_players(
        df,
        available_only=True,
        positions=selected_positions,
        search=search_term,
        sort_by=sort_by,
        ascending=ascending
    )

    # Main area: display available players
    st.subheader("Available Players")
    st.write("Players not yet taken by any manager. Use filters to narrow down the list.")
    # Display a limited number of rows for performance; user can scroll inside the dataframe
    st.dataframe(
        filtered_df[['Player', 'Team', 'Position', 'Weighted Score', 'Points 25/26', 'Goals 25/26', 'Assists 25/26', 'CS 25/26']].head(100),
        height=400
    )

    # Form to add players to wish list or team or mark as taken
    with st.form("add_player"):
        st.write("**Add or mark players**")
        # Provide a drop-down of players based on current filters for ease; but use full available list to allow search
        add_options = filtered_df['Player'].tolist()
        selected_player = st.selectbox("Select player", options=add_options)
        action = st.selectbox("Action", options=["Add to Wish List", "Add to My Team", "Mark as Taken by Others"])
        submit = st.form_submit_button("Apply")
        if submit and selected_player:
            if action == "Add to Wish List":
                if selected_player in st.session_state.wish_list:
                    st.warning(f"{selected_player} is already in your wish list.")
                elif selected_player in st.session_state.my_team:
                    st.warning(f"{selected_player} is already in your team.")
                elif selected_player in st.session_state.taken_players:
                    st.warning(f"{selected_player} has been drafted by another manager.")
                else:
                    st.session_state.wish_list.append(selected_player)
                    st.success(f"Added {selected_player} to your wish list.")
            elif action == "Add to My Team":
                if not can_add_to_team(selected_player, df):
                    st.warning(f"Cannot add {selected_player} to your team due to position limits, duplicates or full team.")
                else:
                    st.session_state.my_team.append(selected_player)
                    # Remove from wish list if present
                    if selected_player in st.session_state.wish_list:
                        st.session_state.wish_list.remove(selected_player)
                    st.success(f"Drafted {selected_player} to your team.")
            elif action == "Mark as Taken by Others":
                if selected_player in st.session_state.taken_players:
                    st.warning(f"{selected_player} was already marked as taken.")
                else:
                    st.session_state.taken_players.append(selected_player)
                    # Remove from wish list or team if necessary
                    if selected_player in st.session_state.wish_list:
                        st.session_state.wish_list.remove(selected_player)
                    if selected_player in st.session_state.my_team:
                        st.session_state.my_team.remove(selected_player)
                    st.success(f"Marked {selected_player} as taken by another manager.")

    # Display current team and wish list
    display_team(df)
    display_wish_list(df)

    # Suggestions based on remaining slots
    pos_counts = count_positions(st.session_state.my_team, df)
    slots_left = remaining_slots(pos_counts)
    display_suggestions(df, slots_left)

    # Sidebar: actions to reset or show taken players
    st.sidebar.header("Utilities")
    if st.sidebar.button("Reset all selections"):
        st.session_state.wish_list.clear()
        st.session_state.my_team.clear()
        st.session_state.taken_players.clear()
        st.sidebar.success("Selections reset.")
    with st.sidebar.expander("Players taken by other managers"):
        if st.session_state.taken_players:
            taken_df = df[df['Player'].isin(st.session_state.taken_players)]
            st.dataframe(taken_df[['Player', 'Team', 'Position', 'Weighted Score']], height=300)
        else:
            st.write("No players marked as taken.")


if __name__ == "__main__":
    main()