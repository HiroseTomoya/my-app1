#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "mpi.h"

#define RANGE (2.0/5.0*M_PI)

int main(int argc, char **argv)
{
    int me, np, n;
    double b_sec, a_sec;
    MPI_Status stat;

    MPI_Init(&argc, &argv);
    MPI_Comm_size(MPI_COMM_WORLD, &np);
    MPI_Comm_rank(MPI_COMM_WORLD, &me);

    if (me == 0){
        n = atoi(argv[1]);
    }

    b_sec = MPI_Wtime();
    MPI_Bcast(&n, 1, MPI_INT, 0, MPI_COMM_WORLD);

    {
        int i;
        long long i_start = (long long)n * me / np;
        long long i_end   = (long long)n * (me + 1) / np;
        double x[2] = {0.0, 0.0};
        double my_b_sec, my_a_sec;

        my_b_sec = MPI_Wtime();
        for (i = i_start; i < i_end; i++)
            x[0] += sin(RANGE*i/n) * (RANGE/n);
        my_a_sec = MPI_Wtime();
        x[1] = my_a_sec - my_b_sec;

        if (me == 0){
            double total = x[0];
            int src;
            for (src = 1; src < np; src++){
                double o_x[2];
                MPI_Recv(o_x, 2, MPI_DOUBLE, src, 11, MPI_COMM_WORLD, &stat);
                total += o_x[0];
                printf("[W] Elapsed time(s): %lf\n", o_x[1]);
            }
            a_sec = MPI_Wtime();
            printf("[M] Elapsed time(s): %lf\n", a_sec - b_sec);
            printf("Result: %25.15lf\n", total);
        } else {
            MPI_Send(x, 2, MPI_DOUBLE, 0, 11, MPI_COMM_WORLD);
        }
    }

    MPI_Finalize();

    if (me == 0)
        printf("area : %25.15lf\n", 1.0 - cos(RANGE));

    return 0;
}
