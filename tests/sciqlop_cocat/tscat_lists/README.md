# Event lists used to build tscat test databases

Three published event lists, copied from cocat-rs (`crates/cocat-server/src/relay/data`), all
under the CC-BY-4.0 licence. `tests/sciqlop_cocat/tscat_databases.py` writes them into a tscat
database, which the tests then import into a cocat-rs project.

- `dimmock_2022_mirror_mode_storms.csv`: Dimmock, A. P. et al. (2022), J. Geophys. Res. 127,
  e2022JA030754, https://doi.org/10.1029/2022JA030754 (Table 1).
- `stawarz_2022_turbulence_intervals.csv`: Stawarz et al. (2022), Phys. Plasmas 29, 012302,
  https://doi.org/10.1063/5.0071106 (supplementary material).
- `fargette_2023_reconnection_exhausts.csv`: Fargette, N., Lavraud, B., Rouillard, A. P. et al.
  (2023), A&A 674, A98, https://doi.org/10.1051/0004-6361/202346043 (Table D.1).

`tscat_0_2_database.sqlite` is not an event list: it is tscat's own test database in its oldest
format (`tests/migration-db-test.sqlite` in tscat), which tscat upgrades when it opens it. The tests
use it to check that the import reads such a database without changing the file.
