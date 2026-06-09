-- Run this in Supabase Dashboard → SQL Editor

create table if not exists camps (
    camp_id          text primary key,
    name             text not null,
    sport            text not null,
    camp_type        text,
    operator_name    text,
    operator_verified boolean default false,
    address          text,
    city             text,
    country_code     text,
    lat              double precision,
    lng              double precision,
    skill_level_min  text,
    skill_level_max  text,
    max_group_size   integer,
    solo_friendly    boolean default true,
    language_of_instruction text[],
    amenities        text[],
    cancellation_policy text,
    source           text,
    average_review_score double precision,
    review_count     integer
);

create table if not exists camp_sessions (
    session_id           text primary key,
    camp_id              text references camps(camp_id) on delete cascade,
    start_date           date not null,
    end_date             date not null,
    capacity             integer,
    spots_remaining      integer,
    price_per_person_eur double precision
);

create table if not exists hotels (
    hotel_id             text primary key,
    name                 text not null,
    city                 text,
    lat                  double precision,
    lng                  double precision,
    stars                integer,
    amenities            text[],
    price_per_night_eur  double precision,
    booking_link         text,
    sport_partner        boolean default false
);

create table if not exists airport_mapping (
    id                  serial primary key,
    city                text not null,
    iata                text not null,
    name                text,
    transfer_time_mins  integer
);
